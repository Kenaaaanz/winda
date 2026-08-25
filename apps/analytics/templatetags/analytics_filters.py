from django import template

register = template.Library()

@register.filter
def pluck(queryset, attribute):
    """
    Extract a list of attribute values from a list of dicts or objects.
    Usage: {{ data|pluck:'month' }}
    """
    if not queryset:
        return []
    
    result = []
    for item in queryset:
        if isinstance(item, dict):
            result.append(item.get(attribute, ''))
        else:
            result.append(getattr(item, attribute, ''))
    return result

@register.filter
def pluck_float(queryset, attribute):
    """
    Extract a list of float values from a list of dicts or objects.
    Usage: {{ data|pluck_float:'amount' }}
    """
    if not queryset:
        return []
    
    result = []
    for item in queryset:
        if isinstance(item, dict):
            value = item.get(attribute, 0)
        else:
            value = getattr(item, attribute, 0)
        try:
            result.append(float(value))
        except (ValueError, TypeError):
            result.append(0)
    return result

@register.filter
def to_json(value):
    """
    Convert a value to JSON string.
    Usage: {{ data|to_json }}
    """
    import json
    try:
        return json.dumps(value)
    except:
        return '[]'