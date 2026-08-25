from django.contrib.admin import AdminSite
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.contrib import admin
from django.urls import reverse
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.properties.models import Property, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.accounts.models import User as CustomUser, OwnerProfile, TenantProfile
from apps.communications.models import ChatRoom, Message


class WindaAdminSite(AdminSite):
    """Custom admin site for Superadmin with platform-wide analytics"""
    
    site_header = 'Winda Super Admin'
    site_title = 'Winda Admin'
    index_title = 'Platform Dashboard'
    site_url = '/'
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with platform stats for superadmin only"""
        # Only superusers can access this
        if not request.user.is_superuser:
            return super().index(request, extra_context)
        
        context = {
            'app_list': self.get_app_list(request),
            'title': self.index_title,
            'subtitle': 'Platform Overview & Analytics',
        }
        
        # Get all platform stats
        context['stats'] = self.get_platform_stats()
        context['recent_activities'] = self.get_recent_activities()
        context['quick_actions'] = self.get_quick_actions()
        
        return super().index(request, context)
    
    def get_platform_stats(self):
        """Get platform-wide statistics for superadmin"""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        last_3_months = today - timedelta(days=90)
        
        # ========================================
        # USER STATS
        # ========================================
        total_users = CustomUser.objects.filter(is_active=True).count()
        new_users_week = CustomUser.objects.filter(date_joined__date__gte=last_week).count()
        new_users_month = CustomUser.objects.filter(date_joined__date__gte=last_month).count()
        
        owners = CustomUser.objects.filter(user_type='HOUSE_OWNER', is_active=True).count()
        tenants = CustomUser.objects.filter(user_type='TENANT', is_active=True).count()
        caretakers = CustomUser.objects.filter(user_type='CARETAKER', is_active=True).count()
        pending_verifications = CustomUser.objects.filter(
            user_type='HOUSE_OWNER',
            verification_status='PENDING'
        ).count()
        
        # ========================================
        # PROPERTY STATS
        # ========================================
        total_properties = Property.objects.count()
        pending_properties = Property.objects.filter(verification_status='PENDING').count()
        verified_properties = Property.objects.filter(verification_status='VERIFIED').count()
        rejected_properties = Property.objects.filter(verification_status='REJECTED').count()
        
        multi_unit_buildings = Property.objects.filter(is_multi_unit=True).count()
        
        # Unit stats
        total_units = Unit.objects.count()
        available_units = Unit.objects.filter(is_available=True).count()
        rented_units = Unit.objects.filter(status='RENTED').count()
        booked_units = Unit.objects.filter(status='BOOKED').count()
        under_maintenance_units = Unit.objects.filter(status='UNDER_MAINTENANCE').count()
        
        # ========================================
        # APPLICATION STATS
        # ========================================
        total_applications = TenantApplication.objects.count()
        pending_applications = TenantApplication.objects.filter(status='PENDING').count()
        under_review_applications = TenantApplication.objects.filter(status='UNDER_REVIEW').count()
        approved_applications = TenantApplication.objects.filter(status='APPROVED').count()
        rejected_applications = TenantApplication.objects.filter(status='REJECTED').count()
        applications_this_month = TenantApplication.objects.filter(
            created_at__date__gte=last_month
        ).count()
        
        # ========================================
        # PAYMENT STATS
        # ========================================
        completed_payments = Payment.objects.filter(status='COMPLETED')
        total_revenue = completed_payments.aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        weekly_revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_week
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        platform_fees = total_revenue * Decimal('0.03')
        pending_payments = Payment.objects.filter(status='PENDING').count()
        failed_payments = Payment.objects.filter(status='FAILED').count()
        
        # ========================================
        # MAINTENANCE STATS
        # ========================================
        total_maintenance = MaintenanceRequest.objects.count()
        pending_maintenance = MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = MaintenanceRequest.objects.filter(status='RESOLVED').count()
        
        # ========================================
        # LEASE STATS
        # ========================================
        total_leases = Lease.objects.count()
        active_leases = Lease.objects.filter(status='ACTIVE').count()
        pending_signature = Lease.objects.filter(status='PENDING_SIGNATURE').count()
        expiring_soon = Lease.objects.filter(
            status='ACTIVE',
            end_date__lte=today + timedelta(days=30)
        ).count()
        
        # ========================================
        # COMMUNICATION STATS
        # ========================================
        total_chat_rooms = ChatRoom.objects.filter(is_active=True).count()
        total_messages = Message.objects.filter(is_deleted=False).count()
        messages_this_week = Message.objects.filter(
            created_at__date__gte=last_week,
            is_deleted=False
        ).count()
        
        return {
            'users': {
                'total': total_users,
                'new_week': new_users_week,
                'new_month': new_users_month,
                'owners': owners,
                'tenants': tenants,
                'caretakers': caretakers,
                'pending_verifications': pending_verifications,
            },
            'properties': {
                'total': total_properties,
                'pending': pending_properties,
                'verified': verified_properties,
                'rejected': rejected_properties,
                'multi_unit': multi_unit_buildings,
                'total_units': total_units,
                'available_units': available_units,
                'rented_units': rented_units,
                'booked_units': booked_units,
                'under_maintenance': under_maintenance_units,
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'under_review': under_review_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
                'this_month': applications_this_month,
            },
            'payments': {
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'weekly_revenue': float(weekly_revenue),
                'platform_fees': float(platform_fees),
                'pending': pending_payments,
                'failed': failed_payments,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
            },
            'leases': {
                'total': total_leases,
                'active': active_leases,
                'pending_signature': pending_signature,
                'expiring_soon': expiring_soon,
            },
            'communications': {
                'chat_rooms': total_chat_rooms,
                'messages': total_messages,
                'messages_this_week': messages_this_week,
            },
            'growth': {
                'new_users': new_users_month,
                'new_properties': Property.objects.filter(created_at__date__gte=last_month).count(),
                'new_applications': applications_this_month,
            }
        }
    
    def get_recent_activities(self):
        """Get recent platform activities for superadmin"""
        activities = []
        
        # Recent users
        recent_users = CustomUser.objects.order_by('-date_joined')[:3]
        for user in recent_users:
            activities.append({
                'type': 'New User',
                'icon': 'user-plus',
                'color': 'blue',
                'description': f'{user.get_full_name()} registered as {user.get_user_type_display()}',
                'time': user.date_joined,
                'time_ago': self.get_time_ago(user.date_joined),
            })
        
        # Recent properties
        recent_properties = Property.objects.order_by('-created_at')[:3]
        for prop in recent_properties:
            status = 'verified' if prop.verification_status == 'VERIFIED' else 'listed'
            activities.append({
                'type': 'Property',
                'icon': 'home',
                'color': 'green',
                'description': f'Property "{prop.title}" {status} by {prop.owner.user.get_full_name()}',
                'time': prop.created_at,
                'time_ago': self.get_time_ago(prop.created_at),
            })
        
        # Recent payments
        recent_payments = Payment.objects.filter(status='COMPLETED').order_by('-paid_at')[:3]
        for payment in recent_payments:
            activities.append({
                'type': 'Payment',
                'icon': 'money-bill-wave',
                'color': 'yellow',
                'description': f'Payment of KES {payment.amount:,.2f} from {payment.payer.get_full_name()}',
                'time': payment.paid_at,
                'time_ago': self.get_time_ago(payment.paid_at),
            })
        
        # Recent applications
        recent_apps = TenantApplication.objects.order_by('-created_at')[:3]
        for app in recent_apps:
            activities.append({
                'type': 'Application',
                'icon': 'file-signature',
                'color': 'purple',
                'description': f'{app.tenant.get_full_name()} applied for {app.property.title}',
                'time': app.created_at,
                'time_ago': self.get_time_ago(app.created_at),
            })
        
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
    def get_quick_actions(self):
        """Get quick actions for superadmin"""
        # Use direct URLs for admin actions
        return [
            {
                'name': 'Manage Users',
                'url': '/admin/accounts/user/',
                'icon': 'fa-users-cog',
                'color': 'blue',
            },
            {
                'name': 'Verify Properties',
                'url': '/admin/properties/property/?verification_status__exact=PENDING',
                'icon': 'fa-check-circle',
                'color': 'yellow',
            },
            {
                'name': 'View All Properties',
                'url': '/admin/properties/property/',
                'icon': 'fa-home',
                'color': 'green',
            },
            {
                'name': 'View Payments',
                'url': '/admin/payments/payment/',
                'icon': 'fa-credit-card',
                'color': 'purple',
            },
            {
                'name': 'Maintenance Requests',
                'url': '/admin/maintenance/maintenancerequest/',
                'icon': 'fa-tools',
                'color': 'red',
            },
            {
                'name': 'Platform Settings',
                'url': '/admin/',
                'icon': 'fa-cog',
                'color': 'gray',
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
            return f'{minutes}m ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours}h ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days}d ago'
        else:
            return time.strftime('%b %d, %Y')


# Create admin site instance
admin_site = WindaAdminSite(name='admin')