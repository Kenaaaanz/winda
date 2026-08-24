from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from apps.properties.models import Property, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.communications.models import Message
from django.contrib.auth import get_user_model

User = get_user_model()

class AnalyticsService:
    """Service for generating analytics data"""
    
    @staticmethod
    def get_owner_dashboard_stats(owner):
        """Get comprehensive stats for an owner"""
        from apps.properties.models import Property
        from apps.tenants.models import TenantApplication, Lease
        from apps.payments.models import Payment
        from apps.maintenance.models import MaintenanceRequest
        
        # Properties
        properties = Property.objects.filter(owner=owner)
        total_properties = properties.count()
        available_properties = properties.filter(availability_status='AVAILABLE').count()
        occupied_properties = properties.filter(availability_status='RENTED').count()
        
        # Units
        total_units = 0
        available_units = 0
        occupied_units = 0
        for prop in properties:
            if prop.is_multi_unit:
                total_units += prop.units.count()
                available_units += prop.units.filter(is_available=True).count()
                occupied_units += prop.units.filter(status='RENTED').count()
            else:
                total_units += 1
                if prop.availability_status == 'AVAILABLE':
                    available_units += 1
                elif prop.availability_status == 'RENTED':
                    occupied_units += 1
        
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Revenue
        payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        )
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Monthly revenue (last 6 months)
        monthly_revenue = []
        today = timezone.now().date()
        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            month_start = month_start.replace(day=1)
            revenue = payments.filter(
                paid_at__date__gte=month_start,
                paid_at__date__lt=month_end
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_revenue.append({
                'month': month_start.strftime('%B'),
                'amount': float(revenue)
            })
        monthly_revenue.reverse()
        
        # Applications
        applications = TenantApplication.objects.filter(property__owner=owner)
        total_applications = applications.count()
        pending_applications = applications.filter(status='PENDING').count()
        approved_applications = applications.filter(status='APPROVED').count()
        rejected_applications = applications.filter(status='REJECTED').count()
        
        application_trend = []
        for i in range(12):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_start = month_start.replace(day=1)
            count = applications.filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_start + timedelta(days=32)
            ).count()
            application_trend.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        application_trend.reverse()
        
        # Maintenance
        maintenance = MaintenanceRequest.objects.filter(property__owner=owner)
        total_maintenance = maintenance.count()
        pending_maintenance = maintenance.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = maintenance.filter(status='RESOLVED').count()
        
        # Recent activities
        recent_activities = AnalyticsService.get_recent_activities(owner)
        
        # Payment stats
        payment_stats = {
            'total': total_revenue,
            'monthly': monthly_revenue[-1]['amount'] if monthly_revenue else 0,
            'pending': Payment.objects.filter(
                property__owner=owner,
                status='PENDING'
            ).count(),
        }
        
        # Tenant stats
        tenant_stats = {
            'total_tenants': Lease.objects.filter(
                property__owner=owner,
                status='ACTIVE'
            ).count(),
            'active_leases': Lease.objects.filter(
                property__owner=owner,
                status='ACTIVE'
            ).count(),
            'expiring_soon': Lease.objects.filter(
                property__owner=owner,
                status='ACTIVE',
                end_date__lte=timezone.now().date() + timedelta(days=30)
            ).count(),
        }
        
        return {
            'properties': {
                'total': total_properties,
                'available': available_properties,
                'occupied': occupied_properties,
                'occupancy_rate': round(occupancy_rate, 1),
                'total_units': total_units,
                'available_units': available_units,
                'occupied_units': occupied_units,
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': monthly_revenue,
                'monthly_current': payment_stats['monthly'],
                'pending_payments': payment_stats['pending'],
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
                'trend': application_trend,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
            },
            'tenants': tenant_stats,
            'recent_activities': recent_activities,
        }
    
    @staticmethod
    def get_platform_stats():
        """Get platform-wide statistics for superadmin"""
        from apps.properties.models import Property
        from apps.tenants.models import TenantApplication, Lease
        from apps.payments.models import Payment
        from apps.maintenance.models import MaintenanceRequest
        
        # User stats
        total_users = User.objects.filter(is_active=True).count()
        owners = User.objects.filter(user_type='HOUSE_OWNER', is_active=True).count()
        tenants = User.objects.filter(user_type='TENANT', is_active=True).count()
        caretakers = User.objects.filter(user_type='CARETAKER', is_active=True).count()
        
        # New users (last 30 days)
        last_30_days = timezone.now() - timedelta(days=30)
        new_users = User.objects.filter(date_joined__gte=last_30_days).count()
        new_owners = User.objects.filter(
            user_type='HOUSE_OWNER',
            date_joined__gte=last_30_days
        ).count()
        new_tenants = User.objects.filter(
            user_type='TENANT',
            date_joined__gte=last_30_days
        ).count()
        
        # Property stats
        total_properties = Property.objects.count()
        verified_properties = Property.objects.filter(verification_status='VERIFIED').count()
        pending_properties = Property.objects.filter(verification_status='PENDING').count()
        multi_unit_properties = Property.objects.filter(is_multi_unit=True).count()
        
        total_units = Unit.objects.count()
        available_units = Unit.objects.filter(is_available=True).count()
        rented_units = Unit.objects.filter(status='RENTED').count()
        
        # Revenue
        payments = Payment.objects.filter(status='COMPLETED')
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        platform_fees = payments.aggregate(total=Sum('amount'))['total'] or 0
        # Assuming 3% platform fee
        platform_revenue = platform_fees * Decimal('0.03')
        
        # Monthly revenue (last 12 months)
        monthly_revenue = []
        today = timezone.now().date()
        for i in range(12):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_start = month_start.replace(day=1)
            revenue = payments.filter(
                paid_at__date__gte=month_start,
                paid_at__date__lt=month_start + timedelta(days=32)
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_revenue.append({
                'month': month_start.strftime('%b %Y'),
                'amount': float(revenue)
            })
        monthly_revenue.reverse()
        
        # Application stats
        applications = TenantApplication.objects.all()
        total_applications = applications.count()
        pending_applications = applications.filter(status='PENDING').count()
        approved_applications = applications.filter(status='APPROVED').count()
        rejected_applications = applications.filter(status='REJECTED').count()
        
        # Lease stats
        active_leases = Lease.objects.filter(status='ACTIVE').count()
        total_leases = Lease.objects.count()
        
        # Maintenance stats
        maintenance = MaintenanceRequest.objects.all()
        total_maintenance = maintenance.count()
        pending_maintenance = maintenance.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = maintenance.filter(status='RESOLVED').count()
        
        # Growth metrics
        growth = {
            'user_growth': new_users,
            'owner_growth': new_owners,
            'tenant_growth': new_tenants,
            'property_growth': Property.objects.filter(created_at__gte=last_30_days).count(),
        }
        
        return {
            'users': {
                'total': total_users,
                'owners': owners,
                'tenants': tenants,
                'caretakers': caretakers,
                'new_users': new_users,
                'new_owners': new_owners,
                'new_tenants': new_tenants,
                'growth': growth,
            },
            'properties': {
                'total': total_properties,
                'verified': verified_properties,
                'pending': pending_properties,
                'multi_unit': multi_unit_properties,
                'total_units': total_units,
                'available_units': available_units,
                'rented_units': rented_units,
            },
            'revenue': {
                'total': float(total_revenue),
                'platform_fees': float(platform_revenue),
                'monthly': monthly_revenue,
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
            },
            'leases': {
                'total': total_leases,
                'active': active_leases,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
            },
        }
    
    @staticmethod
    def get_property_analytics(property_obj):
        """Get detailed analytics for a specific property"""
        from apps.tenants.models import TenantApplication
        from apps.payments.models import Payment
        from apps.maintenance.models import MaintenanceRequest
        
        # Views and engagement
        views = property_obj.view_count
        favorites = property_obj.favorites.count()
        
        # Applications
        applications = TenantApplication.objects.filter(property=property_obj)
        total_applications = applications.count()
        pending = applications.filter(status='PENDING').count()
        approved = applications.filter(status='APPROVED').count()
        rejected = applications.filter(status='REJECTED').count()
        conversion_rate = (approved / total_applications * 100) if total_applications > 0 else 0
        
        # Revenue
        payments = Payment.objects.filter(property=property_obj, status='COMPLETED')
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Monthly revenue
        monthly_revenue = []
        today = timezone.now().date()
        for i in range(6):
            month_start = today.replace(day=1) - timedelta(days=30 * i)
            month_start = month_start.replace(day=1)
            revenue = payments.filter(
                paid_at__date__gte=month_start,
                paid_at__date__lt=month_start + timedelta(days=32)
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_revenue.append({
                'month': month_start.strftime('%B'),
                'amount': float(revenue)
            })
        monthly_revenue.reverse()
        
        # Maintenance
        maintenance = MaintenanceRequest.objects.filter(property=property_obj)
        total_maintenance = maintenance.count()
        pending_maintenance = maintenance.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        
        # Unit stats (if multi-unit)
        unit_stats = None
        if property_obj.is_multi_unit:
            units = property_obj.units.all()
            unit_stats = {
                'total': units.count(),
                'available': units.filter(is_available=True).count(),
                'rented': units.filter(status='RENTED').count(),
                'occupancy_rate': (units.filter(is_available=False).count() / units.count() * 100) if units.count() > 0 else 0,
            }
        
        return {
            'property': {
                'id': str(property_obj.id),
                'title': property_obj.title,
                'views': views,
                'favorites': favorites,
            },
            'applications': {
                'total': total_applications,
                'pending': pending,
                'approved': approved,
                'rejected': rejected,
                'conversion_rate': round(conversion_rate, 1),
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': monthly_revenue,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
            },
            'units': unit_stats,
        }
    
    @staticmethod
    def get_recent_activities(owner, limit=10):
        """Get recent activities for an owner"""
        from apps.properties.models import Property
        from apps.tenants.models import TenantApplication
        from apps.payments.models import Payment
        from apps.maintenance.models import MaintenanceRequest
        
        activities = []
        
        # Recent properties added
        recent_properties = Property.objects.filter(owner=owner).order_by('-created_at')[:5]
        for prop in recent_properties:
            activities.append({
                'type': 'property_created',
                'icon': 'home',
                'description': f'Listed new property: {prop.title}',
                'timestamp': prop.created_at,
                'time_ago': prop.created_at.strftime('%b %d, %Y'),
            })
        
        # Recent applications
        recent_applications = TenantApplication.objects.filter(
            property__owner=owner
        ).order_by('-created_at')[:5]
        for app in recent_applications:
            activities.append({
                'type': 'application_received',
                'icon': 'file-signature',
                'description': f'New application from {app.tenant.get_full_name()} for {app.property.title}',
                'timestamp': app.created_at,
                'time_ago': app.created_at.strftime('%b %d, %Y'),
            })
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        ).order_by('-paid_at')[:5]
        for payment in recent_payments:
            activities.append({
                'type': 'payment_received',
                'icon': 'money-bill-wave',
                'description': f'Payment of KES {payment.amount:,.0f} received from {payment.payer.get_full_name()}',
                'timestamp': payment.paid_at,
                'time_ago': payment.paid_at.strftime('%b %d, %Y'),
            })
        
        # Sort by timestamp and return top N
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:limit]
    
    @staticmethod
    def get_unit_performance(property_obj):
        """Get performance metrics for units in a multi-unit property"""
        if not property_obj.is_multi_unit:
            return None
        
        units = property_obj.units.all()
        performance = []
        
        for unit in units:
            # Get unit's payment history
            payments = Payment.objects.filter(
                unit=unit,
                status='COMPLETED'
            )
            total_rent = payments.aggregate(total=Sum('amount'))['total'] or 0
            
            # Get maintenance requests
            maintenance = MaintenanceRequest.objects.filter(unit=unit)
            
            # Get lease history
            leases = Lease.objects.filter(unit=unit)
            current_lease = leases.filter(status='ACTIVE').first()
            
            performance.append({
                'unit_number': unit.unit_number,
                'status': unit.get_status_display(),
                'bedrooms': unit.bedrooms,
                'bathrooms': unit.bathrooms,
                'rental_price': float(unit.get_rental_price()),
                'total_revenue': float(total_rent),
                'maintenance_count': maintenance.count(),
                'current_tenant': current_lease.tenant.get_full_name() if current_lease else None,
                'is_available': unit.is_available,
            })
        
        return performance