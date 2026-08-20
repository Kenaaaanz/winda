from django import template

register = template.Library()

@register.filter
def filter_by_status(queryset, status):
    """Filter queryset by a boolean field"""
    if not queryset:
        return []
    if status == 'True':
        return [item for item in queryset if getattr(item, 'is_active', False)]
    elif status == 'False':
        return [item for item in queryset if not getattr(item, 'is_active', False)]
    return queryset

@register.filter
def contains(value, arg):
    """Check if a list contains a value"""
    if not value:
        return False
    return arg in value