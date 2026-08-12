from .models import UserProfile
from django.db.models import Sum, Count
from apps.tenants.models import TenantApplication
from apps.properties.models import Property



def user_profile(request):
    """Add user profile to template context"""
    context = {}
    if request.user.is_authenticated:
        try:
            context['user_profile'] = request.user.profile
        except:
            context['user_profile'] = None
    return context

def pending_applications_count(request):
    """Add pending applications count to context for all templates"""
    context = {'pending_count': 0}
    
    if request.user.is_authenticated and hasattr(request.user, 'owner_profile'):
        context['pending_count'] = TenantApplication.objects.filter(
            property__owner=request.user.owner_profile,
            status='PENDING'
        ).count()
    
    return context

from apps.communications.models import ChatRoom

def unread_chat_count(request):
    """Add unread chat count to all templates"""
    context = {'unread_total': 0}
    
    if request.user.is_authenticated:
        chat_rooms = ChatRoom.objects.filter(participants=request.user, is_active=True)
        total_unread = 0
        for room in chat_rooms:
            total_unread += room.get_unread_count(request.user)
        context['unread_total'] = total_unread
    
    return context

def owner_stats(request):
    """Add owner stats to context for all templates"""
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'owner_profile'):
        owner = request.user.owner_profile
        properties = Property.objects.filter(owner=owner)
        
        total_units = 0
        available_units = 0
        for prop in properties:
            if prop.is_multi_unit:
                total_units += prop.units.count()
                available_units += prop.units.filter(is_available=True).count()
            else:
                total_units += 1
                if prop.availability_status == 'AVAILABLE':
                    available_units += 1
        
        context['owner_units'] = {
            'total': total_units,
            'available': available_units
        }
    
    return context