from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import reverse
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.properties.models import Property
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.accounts.models import User as CustomUser


class WindaAdminSite(admin.AdminSite):
    """Custom admin site with Winda branding and dashboard"""
    
    site_header = 'Winda Administration'
    site_title = 'Winda Admin'
    index_title = 'Dashboard'
    site_url = '/'
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with stats cards"""
        context = {
            'app_list': self.get_app_list(request),
            'title': self.index_title,
            'subtitle': 'Property Management Dashboard',
        }
        
        context['stats'] = self.get_admin_stats()
        context['recent_activities'] = self.get_recent_activities()
        context['quick_actions'] = self.get_quick_actions()
        
        return super().index(request, context)
    
    def get_quick_actions(self):
        """Get quick actions for admin dashboard"""
        return [
            {
                'name': 'Add Property',
                'url': '/admin/properties/property/add/',
                'icon': 'fa-plus-circle',
                'color': 'blue',
            },
            {
                'name': 'View Properties',
                'url': '/admin/properties/property/',
                'icon': 'fa-home',
                'color': 'green',
            },
            {
                'name': 'View Users',
                'url': '/admin/accounts/user/',
                'icon': 'fa-users',
                'color': 'purple',
            },
            {
                'name': 'Pending Verifications',
                'url': '/admin/properties/property/?verification_status__exact=PENDING',
                'icon': 'fa-clock',
                'color': 'yellow',
            },
            {
                'name': 'View Payments',
                'url': '/admin/payments/payment/',
                'icon': 'fa-credit-card',
                'color': 'green',
            },
            {
                'name': 'Maintenance Requests',
                'url': '/admin/maintenance/maintenancerequest/',
                'icon': 'fa-tools',
                'color': 'red',
            },
            {
                'name': 'View Tenants',
                'url': '/admin/accounts/tenantprofile/',
                'icon': 'fa-user-friends',
                'color': 'teal',
            },
            {
                'name': 'View Leases',
                'url': '/admin/tenants/lease/',
                'icon': 'fa-file-contract',
                'color': 'purple',
            },
        ]
    
    def get_admin_stats(self):
        """Get statistics for admin dashboard"""
        # ... rest of stats code (same as above) ...
        pass
    
    def get_recent_activities(self):
        """Get recent activities for admin dashboard"""
        # ... rest of activities code (same as above) ...
        pass


# Create admin site instance
admin_site = WindaAdminSite(name='admin')