from django import template

register = template.Library()

@register.filter
def filter_active(caretakers):
    """Filter caretakers by active status"""
    if not caretakers:
        return []
    return [c for c in caretakers if c.is_active]