from django import template

register = template.Library()

@register.filter
def filter_status(queryset, status):
    """Filter queryset by status"""
    if not queryset:
        return []
    return [item for item in queryset if hasattr(item, 'status') and item.status == status]