from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import ChatRoom, Message, MessageTemplate, ChatBlock, UserMessageDeletion
from .forms import ChatRoomForm, MessageForm
from ..properties.models import Property
from ..notifications.models import Notification

User = get_user_model()


@login_required
def chat_list(request):
    """List user's chat rooms with management options"""
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user,
        is_active=True
    ).order_by('-updated_at')
    
    # Handle filters
    filter_type = request.GET.get('filter')
    if filter_type == 'unread':
        # Get rooms with unread messages
        rooms_with_unread = []
        for room in chat_rooms:
            if room.get_unread_count(request.user) > 0:
                rooms_with_unread.append(room.id)
        chat_rooms = chat_rooms.filter(id__in=rooms_with_unread)
    elif filter_type == 'muted':
        chat_rooms = chat_rooms.filter(is_muted=True)
    
    paginator = Paginator(chat_rooms, 10)
    page = request.GET.get('page')
    try:
        chat_rooms_page = paginator.page(page)
    except PageNotAnInteger:
        chat_rooms_page = paginator.page(1)
    except EmptyPage:
        chat_rooms_page = paginator.page(paginator.num_pages)
    
    # Get unread counts for each room
    for room in chat_rooms_page:
        room.unread_count = room.get_unread_count(request.user)
        room.other_participant = room.get_other_participant(request.user)
    
    # Get blocked users for this user
    blocked_users = ChatBlock.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
    
    context = {
        'chat_rooms': chat_rooms_page,
        'filter_type': filter_type,
        'blocked_users': blocked_users,
        'unread_total': sum(room.get_unread_count(request.user) for room in chat_rooms),
    }
    
    return render(request, 'communications/chat_list.html', context)


@login_required
def chat_detail(request, room_id):
    """View chat room details with full management controls"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user, is_active=True)
    other_participant = room.get_other_participant(request.user)
    
    # Check if blocked
    is_blocked = ChatBlock.objects.filter(
        blocker=request.user,
        blocked=other_participant
    ).exists()
    
    is_blocked_by_other = ChatBlock.objects.filter(
        blocker=other_participant,
        blocked=request.user
    ).exists()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'send_message':
            form = MessageForm(request.POST, request.FILES)
            if form.is_valid():
                if is_blocked_by_other:
                    messages.error(request, 'You cannot send messages to this user.')
                    return redirect('communications:chat_detail', room_id=room_id)
                
                message = form.save(commit=False)
                message.room = room
                message.sender = request.user
                message.save()
                
                # Mark as read by sender
                message.mark_as_read(request.user)
                
                # Update room's updated_at
                room.updated_at = timezone.now()
                room.save(update_fields=['updated_at'])
                
                # Notify other participants
                for participant in room.participants.exclude(id=request.user.id):
                    # Check if participant wants notifications
                    # FIX: Use dictionary access for JSONField
                    notification_pref = getattr(participant, 'notification_preferences', {})
                    
                    # Default to True if not set
                    if not notification_pref or notification_pref.get('push_messages', True):
                        Notification.objects.create(
                            user=participant,
                            notification_type='MESSAGE',
                            title=f'New message from {request.user.get_full_name()}',
                            message=message.content[:100],
                            related_object_type='chat_message',
                            related_object_id=str(message.id),
                            data={
                                'chat_room_id': str(room.id),
                                'sender_id': str(request.user.id),
                                'message_preview': message.content[:50]
                            }
                        )
                
                return redirect('communications:chat_detail', room_id=room_id)
        
        elif action == 'mute_room':
            room.is_muted = not room.is_muted
            if room.is_muted:
                room.muted_until = timezone.now() + timezone.timedelta(days=30)
            else:
                room.muted_until = None
            room.save()
            messages.success(request, f'Chat {"muted" if room.is_muted else "unmuted"} successfully.')
            return redirect('communications:chat_detail', room_id=room_id)
        
        elif action == 'block_user':
            ChatBlock.objects.get_or_create(
                blocker=request.user,
                blocked=other_participant
            )
            messages.success(request, f'User {other_participant.get_full_name()} has been blocked.')
            return redirect('communications:chat_list')
        
        elif action == 'unblock_user':
            ChatBlock.objects.filter(
                blocker=request.user,
                blocked=other_participant
            ).delete()
            messages.success(request, f'User {other_participant.get_full_name()} has been unblocked.')
            return redirect('communications:chat_detail', room_id=room_id)
        
        elif action == 'clear_chat':
            # Delete all messages for this user
            messages_in_room = room.messages.filter(is_deleted=False)
            for msg in messages_in_room:
                msg.delete_for_me(request.user)
            messages.success(request, 'Chat history cleared successfully.')
            return redirect('communications:chat_detail', room_id=room_id)
        
        elif action == 'delete_for_everyone':
            message_id = request.POST.get('message_id')
            message = get_object_or_404(Message, id=message_id, sender=request.user)
            message.delete_for_everyone(request.user)
            return JsonResponse({'status': 'success'})
        
        elif action == 'delete_for_me':
            message_id = request.POST.get('message_id')
            message = get_object_or_404(Message, id=message_id, room=room)
            message.delete_for_me(request.user)
            return JsonResponse({'status': 'success'})
        
        elif action == 'add_reaction':
            message_id = request.POST.get('message_id')
            reaction = request.POST.get('reaction')
            message = get_object_or_404(Message, id=message_id, room=room)
            
            if not message.reactions:
                message.reactions = {}
            
            if str(request.user.id) in message.reactions:
                # Remove reaction if same
                if message.reactions[str(request.user.id)] == reaction:
                    del message.reactions[str(request.user.id)]
                else:
                    message.reactions[str(request.user.id)] = reaction
            else:
                message.reactions[str(request.user.id)] = reaction
            
            message.save()
            return JsonResponse({'status': 'success', 'reactions': message.reactions})
    
    else:
        form = MessageForm()
    
    # Get messages with pagination (excluding those deleted for this user)
    messages_list = room.messages.filter(
        is_deleted=False
    ).exclude(
        id__in=UserMessageDeletion.objects.filter(user=request.user).values_list('message_id', flat=True)
    ).order_by('-created_at')
    
    paginator = Paginator(messages_list, 50)
    page = request.GET.get('page')
    try:
        messages_page = paginator.page(page)
    except PageNotAnInteger:
        messages_page = paginator.page(1)
    except EmptyPage:
        messages_page = paginator.page(paginator.num_pages)
    
    # Mark messages as read
    unread_messages = room.messages.exclude(read_by=request.user)
    for msg in unread_messages:
        msg.mark_as_read(request.user)
    
    # Get other participants
    other_participants = room.participants.exclude(id=request.user.id)
    
    context = {
        'room': room,
        'messages': messages_page,
        'form': form,
        'other_participants': other_participants,
        'is_blocked': is_blocked,
        'is_blocked_by_other': is_blocked_by_other,
        'is_muted': room.is_muted,
        'unread_count': room.get_unread_count(request.user),
    }
    
    return render(request, 'communications/chat_detail.html', context)

@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Delete a message (for everyone or just for me)"""
    message = get_object_or_404(Message, id=message_id)
    room = message.room
    
    # Check if user is in the room
    if request.user not in room.participants.all():
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    action = request.POST.get('action', 'for_me')
    
    if action == 'for_everyone' and message.sender == request.user:
        # Only sender can delete for everyone
        message.delete_for_everyone(request.user)
        return JsonResponse({'status': 'success', 'deleted_for': 'everyone'})
    else:
        # Delete for me
        message.delete_for_me(request.user)
        return JsonResponse({'status': 'success', 'deleted_for': 'me'})


@login_required
def start_chat(request, user_id=None, property_id=None):
    """Start a new chat with management options"""
    if user_id:
        participant = get_object_or_404(User, id=user_id)
        
        # Check if blocked
        if ChatBlock.objects.filter(blocker=request.user, blocked=participant).exists():
            messages.error(request, 'You have blocked this user.')
            return redirect('communications:chat_list')
        
        if ChatBlock.objects.filter(blocker=participant, blocked=request.user).exists():
            messages.error(request, 'This user has blocked you.')
            return redirect('communications:chat_list')
        
        # Check if chat already exists
        existing_room = ChatRoom.objects.filter(
            participants=request.user,
            room_type='PRIVATE',
            is_active=True
        ).filter(participants=participant).first()
        
        if existing_room:
            return redirect('communications:chat_detail', room_id=existing_room.id)
        
        # Create new chat
        room = ChatRoom.objects.create(
            name=f"Chat with {participant.get_full_name()}",
            room_type='PRIVATE',
            created_by=request.user
        )
        room.participants.add(request.user, participant)
        room.save()
        
        return redirect('communications:chat_detail', room_id=room.id)
    
    elif property_id:
        property_obj = get_object_or_404(Property, id=property_id)
        owner = property_obj.owner.user
        
        # Check if blocked
        if ChatBlock.objects.filter(blocker=request.user, blocked=owner).exists():
            messages.error(request, 'You have blocked this user.')
            return redirect('properties:detail', pk=property_id)
        
        if ChatBlock.objects.filter(blocker=owner, blocked=request.user).exists():
            messages.error(request, 'This user has blocked you.')
            return redirect('properties:detail', pk=property_id)
        
        # Check if chat already exists
        existing_room = ChatRoom.objects.filter(
            participants=request.user,
            property=property_obj,
            room_type='PROPERTY_INQUIRY',
            is_active=True
        ).filter(participants=owner).first()
        
        if existing_room:
            return redirect('communications:chat_detail', room_id=existing_room.id)
        
        # Create new chat
        room = ChatRoom.objects.create(
            name=f"Inquiry about {property_obj.title}",
            room_type='PROPERTY_INQUIRY',
            property=property_obj,
            created_by=request.user
        )
        room.participants.add(request.user, owner)
        room.save()
        
        # Notify owner
        Notification.objects.create(
            user=owner,
            notification_type='MESSAGE',
            title=f'New inquiry from {request.user.get_full_name()}',
            message=f'{request.user.get_full_name()} is interested in {property_obj.title}',
            related_object_type='chat_room',
            related_object_id=str(room.id),
            data={
                'chat_room_id': str(room.id),
                'property_id': str(property_obj.id),
                'tenant_id': str(request.user.id)
            }
        )
        
        return redirect('communications:chat_detail', room_id=room.id)
    
    return redirect('communications:chat_list')


@login_required
def get_unread_count(request):
    """Get unread messages count for all rooms"""
    chat_rooms = ChatRoom.objects.filter(participants=request.user, is_active=True)
    total_unread = 0
    for room in chat_rooms:
        total_unread += room.get_unread_count(request.user)
    
    return JsonResponse({'count': total_unread})


@login_required
def chat_settings(request, room_id):
    """Manage chat settings for a specific room"""
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user, is_active=True)
    other_participant = room.get_other_participant(request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'mute':
            room.is_muted = not room.is_muted
            if room.is_muted:
                room.muted_until = timezone.now() + timezone.timedelta(days=30)
            else:
                room.muted_until = None
            room.save()
            messages.success(request, f'Chat {"muted" if room.is_muted else "unmuted"} successfully.')
        
        elif action == 'block':
            ChatBlock.objects.get_or_create(
                blocker=request.user,
                blocked=other_participant
            )
            messages.success(request, f'User {other_participant.get_full_name()} has been blocked.')
            return redirect('communications:chat_list')
        
        elif action == 'unblock':
            ChatBlock.objects.filter(
                blocker=request.user,
                blocked=other_participant
            ).delete()
            messages.success(request, f'User {other_participant.get_full_name()} has been unblocked.')
        
        elif action == 'clear_chat':
            messages_in_room = room.messages.filter(is_deleted=False)
            for msg in messages_in_room:
                msg.delete_for_me(request.user)
            messages.success(request, 'Chat history cleared successfully.')
            return redirect('communications:chat_detail', room_id=room_id)
        
        elif action == 'leave_chat':
            room.participants.remove(request.user)
            if room.participants.count() == 0:
                room.is_active = False
                room.save()
            messages.success(request, 'You have left the chat.')
            return redirect('communications:chat_list')
        
        return redirect('communications:chat_settings', room_id=room_id)
    
    is_blocked = ChatBlock.objects.filter(
        blocker=request.user,
        blocked=other_participant
    ).exists()
    
    is_blocked_by_other = ChatBlock.objects.filter(
        blocker=other_participant,
        blocked=request.user
    ).exists()
    
    context = {
        'room': room,
        'other_participant': other_participant,
        'is_blocked': is_blocked,
        'is_blocked_by_other': is_blocked_by_other,
        'is_muted': room.is_muted,
        'message_count': room.messages.filter(is_deleted=False).count(),
    }
    
    return render(request, 'communications/chat_settings.html', context)


@login_required
def blocked_users(request):
    """View and manage blocked users"""
    blocked_list = ChatBlock.objects.filter(blocker=request.user).select_related('blocked')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            ChatBlock.objects.filter(
                blocker=request.user,
                blocked_id=user_id
            ).delete()
            messages.success(request, 'User unblocked successfully.')
            return redirect('communications:blocked_users')
    
    paginator = Paginator(blocked_list, 20)
    page = request.GET.get('page')
    try:
        blocked_page = paginator.page(page)
    except PageNotAnInteger:
        blocked_page = paginator.page(1)
    except EmptyPage:
        blocked_page = paginator.page(paginator.num_pages)
    
    return render(request, 'communications/blocked_users.html', {
        'blocked_users': blocked_page,
    })

@login_required
def recent_chats(request):
    """Get recent chats for the floating chat button"""
    chat_rooms = ChatRoom.objects.filter(
        participants=request.user,
        is_active=True
    ).order_by('-updated_at')[:5]
    
    chats = []
    for room in chat_rooms:
        other_participant = room.get_other_participant(request.user)
        last_message = room.get_last_message()
        unread_count = room.get_unread_count(request.user)
        
        if other_participant:
            chats.append({
                'id': str(room.id),
                'other_participant_name': other_participant.get_full_name(),
                'other_participant_initials': other_participant.get_full_name()[:1].upper(),
                'last_message': last_message.content[:50] if last_message else 'No messages yet',
                'unread_count': unread_count,
                'updated_at': room.updated_at.isoformat()
            })
    
    return JsonResponse({'chats': chats})