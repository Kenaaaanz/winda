from django.shortcuts import redirect
from .models import SeoMeta, SeoRedirect

class SeoMiddleware:
    """Middleware for SEO redirects and meta data"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Handle redirects
        redirect_obj = SeoRedirect.objects.filter(
            old_path=request.path,
            is_active=True
        ).first()
        
        if redirect_obj:
            return redirect(redirect_obj.new_path, permanent=redirect_obj.redirect_type == '301')
        
        response = self.get_response(request)
        
        # Add meta tags to response
        if hasattr(request, 'seo_meta'):
            response.seo_meta = request.seo_meta
        
        return response