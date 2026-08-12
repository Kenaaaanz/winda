from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def filter_today(queryset):
    """Filter queryset to items created today"""
    if not queryset:
        return []
    today = timezone.now().date()
    return [item for item in queryset if hasattr(item, 'created_at') and item.created_at.date() == today]

@register.filter
def avg_wait_time(queryset):
    """Calculate average wait time for pending applications"""
    if not queryset:
        return 0
    
    total_days = 0
    count = 0
    today = timezone.now().date()
    
    for item in queryset:
        if hasattr(item, 'created_at'):
            days = (today - item.created_at.date()).days
            total_days += days
            count += 1
    
    return round(total_days / count) if count > 0 else 0

@register.filter
def filter_status(queryset, status):
    """
    Filter a list or queryset by status field.
    Works with both querysets and lists of objects with a 'status' attribute.
    """
    if not queryset:
        return []
    
    # If it's a queryset of model objects
    if hasattr(queryset, 'model'):
        return queryset.filter(status=status)
    
    # If it's a list of objects
    return [item for item in queryset if hasattr(item, 'status') and item.status == status]

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if not dictionary:
        return ''
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def dictsort(queryset, field):
    """
    Sort a list of dicts by a field.
    This is a replacement for Django's dictsort that works with our tenant list.
    """
    if not queryset:
        return []
    
    # If it's a list of dicts
    if queryset and isinstance(queryset[0], dict):
        return sorted(queryset, key=lambda x: x.get(field, ''))
    
    # If it's a Django queryset, use the built-in dictsort
    from django.template.defaultfilters import dictsort as django_dictsort
    return django_dictsort(queryset, field)

@register.filter
def contains(value, arg):
    """Check if a list contains a value"""
    if not value:
        return False
    return arg in value