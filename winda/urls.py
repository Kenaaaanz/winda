from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from apps.accounts.views import dashboard 
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from apps.properties.models import Property
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.shortcuts import render
from apps.admin_extended.admin import admin_site

User = get_user_model()

# Custom home view with context
def home_view(request):
    """Home page with dynamic statistics"""
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

urlpatterns = [
    # Admin
    path('admin/', admin_site.urls),
    
    # Home
    path('', home_view, name='home'),


    # Dashboard - Direct URL
    path('dashboard/', login_required(dashboard), name='dashboard'),  
    
    # Apps
    path('accounts/', include('apps.accounts.urls')),
    path('properties/', include('apps.properties.urls')),
    path('tenants/', include('apps.tenants.urls')),
    path('payments/', include('apps.payments.urls')),
    path('communications/', include('apps.communications.urls')),
    path('maintenance/', include('apps.maintenance.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('notifications/', include('apps.notifications.urls')),

    # Legal
    path('legal/', include('apps.legal.urls')),
    
    # SEO
    path('', include('apps.seo.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)