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


class WindaAdminSite(admin.AdminSite):
    """Custom admin site with Winda branding and comprehensive dashboard"""
    
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
        
        # Get all stats
        context['stats'] = self.get_admin_stats()
        context['recent_activities'] = self.get_recent_activities()
        context['quick_actions'] = self.get_quick_actions()
        context['chart_data'] = self.get_chart_data()
        
        return super().index(request, context)
    
    def get_admin_stats(self):
        """Get comprehensive statistics for admin dashboard"""
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
        
        # Pending verifications
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
        
        # Property types
        property_types = {}
        for prop_type, _ in Property.PROPERTY_TYPES:
            count = Property.objects.filter(property_type=prop_type).count()
            if count > 0:
                property_types[prop_type] = count
        
        # Multi-unit stats
        multi_unit_buildings = Property.objects.filter(is_multi_unit=True).count()
        single_units = Property.objects.filter(is_multi_unit=False).count()
        
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
        
        # Applications this month
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
        
        # Platform fees (3%)
        platform_fees = total_revenue * Decimal('0.03')
        
        pending_payments = Payment.objects.filter(status='PENDING').count()
        failed_payments = Payment.objects.filter(status='FAILED').count()
        
        # Payment by type
        payment_types = {}
        for pay_type, _ in Payment.PAYMENT_TYPES:
            count = Payment.objects.filter(payment_type=pay_type, status='COMPLETED').count()
            amount = Payment.objects.filter(payment_type=pay_type, status='COMPLETED').aggregate(
                total=Sum('amount')
            )['total'] or 0
            if count > 0:
                payment_types[pay_type] = {
                    'count': count,
                    'amount': float(amount)
                }
        
        # ========================================
        # MAINTENANCE STATS
        # ========================================
        total_maintenance = MaintenanceRequest.objects.count()
        pending_maintenance = MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = MaintenanceRequest.objects.filter(status='RESOLVED').count()
        closed_maintenance = MaintenanceRequest.objects.filter(status='CLOSED').count()
        
        # Maintenance by category
        maintenance_categories = {}
        for category, _ in MaintenanceRequest.CATEGORIES:
            count = MaintenanceRequest.objects.filter(category=category).count()
            if count > 0:
                maintenance_categories[category] = count
        
        # Maintenance by priority
        maintenance_priorities = {}
        for priority, _ in MaintenanceRequest.PRIORITY_LEVELS:
            count = MaintenanceRequest.objects.filter(priority=priority).count()
            if count > 0:
                maintenance_priorities[priority] = count
        
        # Average resolution time (in hours)
        resolved_requests = MaintenanceRequest.objects.filter(
            status='RESOLVED',
            resolved_at__isnull=False
        )
        total_hours = 0
        for req in resolved_requests:
            if req.resolved_at and req.created_at:
                time_diff = req.resolved_at - req.created_at
                total_hours += time_diff.total_seconds() / 3600
        
        avg_resolution_time = total_hours / resolved_requests.count() if resolved_requests.count() > 0 else 0
        
        # ========================================
        # LEASE STATS
        # ========================================
        total_leases = Lease.objects.count()
        active_leases = Lease.objects.filter(status='ACTIVE').count()
        pending_signature = Lease.objects.filter(status='PENDING_SIGNATURE').count()
        expired_leases = Lease.objects.filter(status='EXPIRED').count()
        terminated_leases = Lease.objects.filter(status='TERMINATED').count()
        
        # Leases expiring soon (next 30 days)
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
        
        # ========================================
        # GROWTH STATS
        # ========================================
        growth = {
            'users': {
                'total': total_users,
                'new_week': new_users_week,
                'new_month': new_users_month,
            },
            'properties': {
                'new_month': Property.objects.filter(created_at__date__gte=last_month).count(),
                'new_week': Property.objects.filter(created_at__date__gte=last_week).count(),
            },
            'applications': {
                'new_month': applications_this_month,
            },
            'revenue': {
                'monthly': float(monthly_revenue),
                'weekly': float(weekly_revenue),
            }
        }
        
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
                'types': property_types,
                'multi_unit': multi_unit_buildings,
                'single_units': single_units,
                'total_units': total_units,
                'available_units': available_units,
                'rented_units': rented_units,
                'booked_units': booked_units,
                'under_maintenance_units': under_maintenance_units,
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
                'types': payment_types,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
                'closed': closed_maintenance,
                'categories': maintenance_categories,
                'priorities': maintenance_priorities,
                'avg_resolution_time': round(avg_resolution_time, 1),
            },
            'leases': {
                'total': total_leases,
                'active': active_leases,
                'pending_signature': pending_signature,
                'expired': expired_leases,
                'terminated': terminated_leases,
                'expiring_soon': expiring_soon,
            },
            'communications': {
                'chat_rooms': total_chat_rooms,
                'messages': total_messages,
                'messages_this_week': messages_this_week,
            },
            'growth': growth,
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
                'badge': user.get_user_type_display() if hasattr(user, 'get_user_type_display') else 'User'
            })
        
        # Recent properties
        recent_properties = Property.objects.order_by('-created_at')[:5]
        for prop in recent_properties:
            status_text = 'listed' if prop.verification_status == 'PENDING' else 'verified'
            activities.append({
                'type': 'property',
                'icon': 'home',
                'color': 'green' if prop.verification_status == 'VERIFIED' else 'yellow',
                'description': f'Property {status_text}: {prop.title}',
                'time': prop.created_at,
                'time_ago': self.get_time_ago(prop.created_at),
                'badge': prop.get_property_type_display() if hasattr(prop, 'get_property_type_display') else 'Property'
            })
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            status='COMPLETED'
        ).order_by('-paid_at')[:5]
        for payment in recent_payments:
            activities.append({
                'type': 'payment',
                'icon': 'money-bill-wave',
                'color': 'green',
                'description': f'Payment of KES {payment.amount:,.2f} received from {payment.payer.get_full_name()}',
                'time': payment.paid_at,
                'time_ago': self.get_time_ago(payment.paid_at),
                'badge': payment.get_payment_type_display() if hasattr(payment, 'get_payment_type_display') else 'Payment'
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
                'badge': app.get_status_display() if hasattr(app, 'get_status_display') else 'Application'
            })
        
        # Sort by time and return top 10
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
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
    
    def get_chart_data(self):
        """Get data for charts"""
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        
        # Revenue by day (last 30 days)
        revenue_by_day = []
        for i in range(30):
            date = today - timedelta(days=i)
            revenue = Payment.objects.filter(
                status='COMPLETED',
                paid_at__date=date
            ).aggregate(total=Sum('amount'))['total'] or 0
            revenue_by_day.append({
                'date': date.strftime('%b %d'),
                'amount': float(revenue)
            })
        revenue_by_day.reverse()
        
        # New users by day (last 30 days)
        users_by_day = []
        for i in range(30):
            date = today - timedelta(days=i)
            count = CustomUser.objects.filter(
                date_joined__date=date
            ).count()
            users_by_day.append({
                'date': date.strftime('%b %d'),
                'count': count
            })
        users_by_day.reverse()
        
        # Applications by day (last 30 days)
        apps_by_day = []
        for i in range(30):
            date = today - timedelta(days=i)
            count = TenantApplication.objects.filter(
                created_at__date=date
            ).count()
            apps_by_day.append({
                'date': date.strftime('%b %d'),
                'count': count
            })
        apps_by_day.reverse()
        
        return {
            'revenue': revenue_by_day,
            'users': users_by_day,
            'applications': apps_by_day,
        }
    
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