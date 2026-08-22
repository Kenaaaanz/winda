from django.conf import settings
from .models import SeoMeta

def seo_settings(request):
    """Add SEO and analytics settings to all templates"""
    from .models import SeoMeta
    
    # Get SEO meta for current path
    seo_meta = None
    try:
        seo_meta = SeoMeta.objects.filter(url_path=request.path).first()
    except:
        pass
    
    # Default SEO if not found
    if not seo_meta:
        seo_meta = {
            'meta_title': 'Winda - Your Home, Directly',
            'meta_description': 'Find and rent properties directly from owners. No agents, just direct connections.',
            'meta_keywords': 'property rental, house hunting, direct renting, Kenya properties, Winda',
        }
    
    return {
        'seo': seo_meta,
        'gtm_container_id': getattr(settings, 'GTM_CONTAINER_ID', ''),
        'ga_measurement_id': getattr(settings, 'GA_MEASUREMENT_ID', ''),
        'site_url': getattr(settings, 'SITE_URL', 'https://www.winda.africa'),
    }