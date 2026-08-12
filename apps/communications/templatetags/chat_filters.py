from django import template

register = template.Library()

@register.filter
def in_list(value, arg):
    """
    Check if a value is in a list/queryset.
    Usage: {{ value|in:list }}
    """
    if value is None or arg is None:
        return False
    return value in arg

@register.filter
def is_in(value, arg):
    """
    Alias for in_list.
    Usage: {{ value|is_in:list }}
    """
    return in_list(value, arg)

@register.filter
def not_in(value, arg):
    """
    Check if a value is not in a list/queryset.
    Usage: {{ value|not_in:list }}
    """
    return not in_list(value, arg)