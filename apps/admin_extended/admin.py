from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from apps.properties.models import Property
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.accounts.models import User as CustomUser, OwnerProfile, TenantProfile


class WindaAdminSite(AdminSite):
    """Custom admin site with Winda branding and dashboard"""
    
    site_header = 'Winda Administration'
    site_title = 'Winda Admin'
    index_title = 'Dashboard'
    site_url = '/'
    
    def get_app_list(self, request):
        """Get app list with custom ordering"""
        app_list = super().get_app_list(request)
        
        # Custom order for apps
        custom_order = [
            'accounts',
            'properties',
            'tenants',
            'payments',
            'maintenance',
            'communications',
            'analytics',
            'notifications',
        ]
        
        # Sort apps by custom order
        app_dict = {app['app_label']: app for app in app_list}
        sorted_apps = []
        for app_label in custom_order:
            if app_label in app_dict:
                sorted_apps.append(app_dict[app_label])
        
        # Add any remaining apps
        for app in app_list:
            if app['app_label'] not in custom_order:
                sorted_apps.append(app)
        
        return sorted_apps
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with stats cards"""
        context = {
            'app_list': self.get_app_list(request),
            'title': self.index_title,
            'subtitle': 'Property Management Dashboard',
        }
        
        # Get stats
        context['stats'] = self.get_admin_stats()
        context['recent_activities'] = self.get_recent_activities()
        context['quick_actions'] = self.get_quick_actions()
        
        return super().index(request, context)
    
    def get_admin_stats(self):
        """Get statistics for admin dashboard"""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        
        # User stats
        total_users = CustomUser.objects.filter(is_active=True).count()
        new_users = CustomUser.objects.filter(date_joined__date__gte=last_week).count()
        owners = CustomUser.objects.filter(user_type='HOUSE_OWNER').count()
        tenants = CustomUser.objects.filter(user_type='TENANT').count()
        
        # Property stats
        total_properties = Property.objects.count()
        pending_verification = Property.objects.filter(verification_status='PENDING').count()
        verified_properties = Property.objects.filter(verification_status='VERIFIED').count()
        multi_unit = Property.objects.filter(is_multi_unit=True).count()
        
        # Unit stats
        total_units = 0
        available_units = 0
        for prop in Property.objects.all():
            if prop.is_multi_unit:
                total_units += prop.units.count()
                available_units += prop.units.filter(is_available=True).count()
            else:
                total_units += 1
                if prop.availability_status == 'AVAILABLE':
                    available_units += 1
        
        # Application stats
        pending_applications = TenantApplication.objects.filter(status='PENDING').count()
        total_applications = TenantApplication.objects.count()
        
        # Payment stats
        total_revenue = Payment.objects.filter(
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Maintenance stats
        pending_maintenance = MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        total_maintenance = MaintenanceRequest.objects.count()
        
        # Lease stats
        active_leases = Lease.objects.filter(status='ACTIVE').count()
        
        return {
            'users': {
                'total': total_users,
                'new': new_users,
                'owners': owners,
                'tenants': tenants,
            },
            'properties': {
                'total': total_properties,
                'pending_verification': pending_verification,
                'verified': verified_properties,
                'multi_unit': multi_unit,
                'total_units': total_units,
                'available_units': available_units,
            },
            'applications': {
                'pending': pending_applications,
                'total': total_applications,
            },
            'payments': {
                'total_revenue': total_revenue,
                'monthly_revenue': monthly_revenue,
            },
            'maintenance': {
                'pending': pending_maintenance,
                'total': total_maintenance,
            },
            'leases': {
                'active': active_leases,
            },
        }
    
    def get_recent_activities(self):
        """Get recent activities for admin dashboard"""
        activities = []
        
        # Recent users
        recent_users = CustomUser.objects.order_by('-date_joined')[:5]
        for user in recent_users:
            activities.append({
                'type': 'user',
                'icon': 'user-plus',
                'color': 'blue',
                'description': f'New user registered: {user.get_full_name()}',
                'time': user.date_joined,
                'time_ago': self.get_time_ago(user.date_joined),
            })
        
        # Recent properties
        recent_properties = Property.objects.order_by('-created_at')[:5]
        for prop in recent_properties:
            activities.append({
                'type': 'property',
                'icon': 'home',
                'color': 'green',
                'description': f'New property listed: {prop.title}',
                'time': prop.created_at,
                'time_ago': self.get_time_ago(prop.created_at),
            })
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            status='COMPLETED'
        ).order_by('-paid_at')[:5]
        for payment in recent_payments:
            activities.append({
                'type': 'payment',
                'icon': 'money-bill-wave',
                'color': 'yellow',
                'description': f'Payment of KES {payment.amount:,.2f} received',
                'time': payment.paid_at,
                'time_ago': self.get_time_ago(payment.paid_at),
            })
        
        # Recent applications
        recent_apps = TenantApplication.objects.order_by('-created_at')[:5]
        for app in recent_apps:
            activities.append({
                'type': 'application',
                'icon': 'file-signature',
                'color': 'purple',
                'description': f'New application from {app.tenant.get_full_name()} for {app.property.title}',
                'time': app.created_at,
                'time_ago': self.get_time_ago(app.created_at),
            })
        
        # Sort by time and return top 10
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
    def get_quick_actions(self):
        """Get quick actions for admin dashboard with correct URL names"""
        # Use the correct Django admin URL names
        return [
            {
                'name': 'Add Property',
                'url': reverse('admin:properties_property_add'),
                'icon': 'fa-plus-circle',
                'color': 'blue',
            },
            {
                'name': 'View Properties',
                'url': reverse('admin:properties_property_changelist'),
                'icon': 'fa-home',
                'color': 'green',
            },
            {
                'name': 'View Users',
                'url': reverse('admin:accounts_user_changelist'),
                'icon': 'fa-users',
                'color': 'purple',
            },
            {
                'name': 'Pending Verifications',
                'url': reverse('admin:properties_property_changelist') + '?verification_status__exact=PENDING',
                'icon': 'fa-clock',
                'color': 'yellow',
            },
            {
                'name': 'View Payments',
                'url': reverse('admin:payments_payment_changelist'),
                'icon': 'fa-credit-card',
                'color': 'green',
            },
            {
                'name': 'Maintenance Requests',
                'url': reverse('admin:maintenance_maintenancerequest_changelist'),
                'icon': 'fa-tools',
                'color': 'red',
            },
            {
                'name': 'View Tenants',
                'url': reverse('admin:accounts_tenantprofile_changelist'),
                'icon': 'fa-user-friends',
                'color': 'teal',
            },
            {
                'name': 'View Leases',
                'url': reverse('admin:tenants_lease_changelist'),
                'icon': 'fa-file-contract',
                'color': 'purple',
            },
        ]
    
    def get_time_ago(self, time):
        """Get time ago string"""
        if not time:
            return ''
        diff = timezone.now() - time
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days} day{"s" if days > 1 else ""} ago'
        else:
            return time.strftime('%b %d, %Y')


# Create admin site instance
admin_site = WindaAdminSite(name='admin')