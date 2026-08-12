from django.utils import timezone
from .models import UserActivity

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            # Update last activity
            request.user.last_activity = timezone.now()
            request.user.save(update_fields=['last_activity'])
            
            # Log user activity for specific actions
            if request.method in ['POST', 'PUT', 'DELETE']:
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='UPDATE' if request.method == 'PUT' else 'CREATE' if request.method == 'POST' else 'DELETE',
                    description=f"{request.method} {request.path}",
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/admin') or request.path.startswith('/static'):
            return self.get_response(request)
        
        # Check for maintenance mode (from settings or cache)
        from django.conf import settings
        if getattr(settings, 'MAINTENANCE_MODE', False):
            from django.shortcuts import render
            return render(request, 'maintenance.html', status=503)
        
        return self.get_response(request)