from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q

from .models import Notification, NotificationPreference
from .forms import NotificationPreferenceForm


@login_required
def notification_list(request):
    """List user's notifications"""
    notifications = Notification.objects.filter(user=request.user)
    
    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter and type_filter != 'all':
        notifications = notifications.filter(notification_type=type_filter)
    
    # Filter by read status
    read_filter = request.GET.get('read')
    if read_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page')
    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)
    
    # Get unread count for badge
    unread_count = Notification.get_unread_count(request.user)
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications_page,
        'type_filter': type_filter,
        'read_filter': read_filter,
        'unread_count': unread_count,
        'notification_types': Notification.NOTIFICATION_TYPES,
    })


@login_required
def notification_detail(request, pk):
    """View notification details"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    # Mark as read if not already
    if not notification.is_read:
        notification.mark_as_read()
    
    return render(request, 'notifications/detail.html', {
        'notification': notification,
    })


@login_required
@require_http_methods(["POST"])
def mark_read(request, pk):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    return JsonResponse({'status': 'success'})


@login_required
@require_http_methods(["POST"])
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    return JsonResponse({'status': 'success'})


@login_required
@require_http_methods(["POST"])
def archive_notification(request, pk):
    """Archive a notification"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.archive()
    return JsonResponse({'status': 'success'})


@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    preference, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification preferences updated successfully!')
            return redirect('notifications:preferences')
    else:
        form = NotificationPreferenceForm(instance=preference)
    
    return render(request, 'notifications/preferences.html', {
        'form': form,
    })


@login_required
def get_unread_count(request):
    """API endpoint for unread notification count"""
    count = Notification.get_unread_count(request.user)
    return JsonResponse({'count': count})