from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from apps.accounts.views import dashboard 
from apps.properties.models import Property
from apps.tenants.models import TenantApplication, Lease
from apps.maintenance.models import MaintenanceRequest
from apps.payments.models import Payment
from apps.communications.models import Message
from django.contrib.auth import get_user_model
from apps.admin_extended.admin import admin_site

User = get_user_model()


# ========================================
# API ENDPOINT FOR REAL-TIME STATS
# ========================================

def admin_stats_api(request):
    """API endpoint for real-time admin stats"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    data = {
        'total_users': User.objects.filter(is_active=True).count(),
        'total_properties': Property.objects.count(),
        'active_leases': Lease.objects.filter(status='ACTIVE').count(),
        'pending_maintenance': MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count(),
        'messages_today': Message.objects.filter(
            created_at__date=today,
            is_deleted=False
        ).count(),
        'new_applications': TenantApplication.objects.filter(
            created_at__date=today
        ).count(),
        'payments_today': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date=today
        ).count(),
        'revenue_30_days': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_30_days
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'new_users_30_days': User.objects.filter(
            date_joined__date__gte=last_30_days
        ).count(),
    }
    
    return JsonResponse(data)


# ========================================
# CUSTOM HOME VIEW
# ========================================

def home_view(request):
    """Home page with dynamic statistics"""
    from django.shortcuts import render
    
    # Get featured properties (verified, available, with images)
    featured_properties = Property.objects.filter(
        verification_status='VERIFIED',
        is_featured=True
    ).order_by('-created_at')[:8]
    
    # If no featured properties, get any verified properties
    if not featured_properties:
        featured_properties = Property.objects.filter(
            verification_status='VERIFIED'
        ).order_by('-created_at')[:8]
    
    # Calculate total units across all properties
    total_units = 0
    for prop in Property.objects.filter(verification_status='VERIFIED'):
        if prop.is_multi_unit:
            total_units += prop.units.count()
        else:
            total_units += 1
    
    context = {
        'featured_properties': featured_properties,
        'total_properties': Property.objects.filter(verification_status='VERIFIED').count(),
        'total_units': total_units,
        'total_tenants': User.objects.filter(user_type='TENANT', is_active=True).count(),
        'total_owners': User.objects.filter(user_type='HOUSE_OWNER', is_active=True).count(),
    }
    
    return render(request, 'home.html', context)


# ========================================
# API SCHEMA VIEW
# ========================================

schema_view = get_schema_view(
    openapi.Info(
        title="Winda API",
        default_version='v1',
        description="API documentation for Winda - Direct Property Rental Platform",
        terms_of_service="https://www.winda.co.ke/terms/",
        contact=openapi.Contact(email="support@winda.co.ke"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


# ========================================
# URL PATTERNS
# ========================================

urlpatterns = [
    # ========================================
    # ADMIN - Use custom admin site
    # ========================================
    path('admin/', admin.site.urls),
    
    # Admin API endpoint for real-time stats
    path('admin/api/stats/', admin_stats_api, name='admin_stats_api'),
    
    # ========================================
    # HOME
    # ========================================
    path('', home_view, name='home'),
    
    # ========================================
    # DASHBOARD
    # ========================================
    path('dashboard/', login_required(dashboard), name='dashboard'),
    
    # ========================================
    # APP URLS
    # ========================================
    path('accounts/', include('apps.accounts.urls')),
    path('properties/', include('apps.properties.urls')),
    path('tenants/', include('apps.tenants.urls')),
    path('payments/', include('apps.payments.urls')),
    path('communications/', include('apps.communications.urls')),
    path('maintenance/', include('apps.maintenance.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('notifications/', include('apps.notifications.urls')),
    
    # ========================================
    # LEGAL
    # ========================================
    path('legal/', include('apps.legal.urls')),
    
    # ========================================
    # SEO
    # ========================================
    path('', include('apps.seo.urls')),
    
    # ========================================
    # API DOCUMENTATION
    # ========================================
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]


# ========================================
# STATIC & MEDIA FILES (Development)
# ========================================

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug Toolbar - Only if installed
    #try:
        #import debug_toolbar
        #urlpatterns = [
            #path('__debug__/', include(debug_toolbar.urls)),
        #] + urlpatterns
    #except ImportError:
        # Debug toolbar not installed, skip it
        #pass


# ========================================
# ERROR HANDLING (Optional - comment out if error handlers don't exist)
# ========================================

 #handler404 = 'apps.common.views.handler404'
 #handler500 = 'apps.common.views.handler500'