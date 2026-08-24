from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from apps.properties.models import Property, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.accounts.models import OwnerProfile, User

class AnalyticsService:
    """Service for generating analytics data"""
    
    @staticmethod
    def get_owner_dashboard_stats(owner):
        """Get comprehensive stats for owner dashboard"""
        from apps.properties.models import Property
        from apps.tenants.models import TenantApplication, Lease
        from apps.payments.models import Payment
        from apps.maintenance.models import MaintenanceRequest
        
        # Property stats
        properties = Property.objects.filter(owner=owner)
        total_properties = properties.count()
        occupied = properties.filter(availability_status='RENTED').count()
        available = properties.filter(availability_status='AVAILABLE').count()
        
        # Unit stats
        total_units = 0
        occupied_units = 0
        for prop in properties:
            if prop.is_multi_unit:
                total_units += prop.units.count()
                occupied_units += prop.units.filter(status='RENTED').count()
            else:
                total_units += 1
                if prop.availability_status == 'RENTED':
                    occupied_units += 1
        
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Tenant stats
        total_tenants = TenantApplication.objects.filter(
            property__owner=owner,
            status='APPROVED'
        ).values('tenant').distinct().count()
        
        pending_applications = TenantApplication.objects.filter(
            property__owner=owner,
            status='PENDING'
        ).count()
        
        # Payment stats
        payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        )
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Monthly revenue (last 6 months)
        monthly_revenue = []
        for i in range(6):
            month_start = timezone.now() - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            revenue = Payment.objects.filter(
                property__owner=owner,
                status='COMPLETED',
                paid_at__gte=month_start,
                paid_at__lt=month_end
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_revenue.append({
                'month': month_start.strftime('%B'),
                'revenue': float(revenue)
            })
        
        # Maintenance stats
        maintenance = MaintenanceRequest.objects.filter(property__owner=owner)
        pending_maintenance = maintenance.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
        resolved_maintenance = maintenance.filter(status='RESOLVED').count()
        
        # Property performance (top 5)
        property_performance = []
        for prop in properties[:5]:
            property_performance.append({
                'title': prop.title,
                'occupancy': prop.availability_status == 'RENTED',
                'tenants': TenantApplication.objects.filter(property=prop, status='APPROVED').count(),
                'revenue': Payment.objects.filter(property=prop, status='COMPLETED').aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                'maintenance': MaintenanceRequest.objects.filter(property=prop).count(),
            })
        
        return {
            'total_properties': total_properties,
            'occupied': occupied,
            'available': available,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'occupancy_rate': round(occupancy_rate, 1),
            'total_tenants': total_tenants,
            'pending_applications': pending_applications,
            'total_revenue': total_revenue,
            'monthly_revenue': monthly_revenue,
            'pending_maintenance': pending_maintenance,
            'resolved_maintenance': resolved_maintenance,
            'property_performance': property_performance,
        }
    
    @staticmethod
    def get_admin_dashboard_stats():
        """Get comprehensive stats for admin dashboard"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # User stats
        total_users = User.objects.filter(is_active=True).count()
        total_owners = User.objects.filter(user_type='HOUSE_OWNER', is_active=True).count()
        total_tenants = User.objects.filter(user_type='TENANT', is_active=True).count()
        pending_verifications = User.objects.filter(
            user_type='HOUSE_OWNER',
            verification_status='PENDING'
        ).count()
        
        # Property stats
        total_properties = Property.objects.count()
        verified_properties = Property.objects.filter(verification_status='VERIFIED').count()
        pending_properties = Property.objects.filter(verification_status='PENDING').count()
        
        # Platform stats
        total_payments = Payment.objects.filter(status='COMPLETED').count()
        total_revenue = Payment.objects.filter(status='COMPLETED').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        platform_fees = Payment.objects.filter(
            status='COMPLETED'
        ).aggregate(
            total_fees=Sum('amount') * Decimal('0.03')
        )['total_fees'] or 0
        
        # Application stats
        total_applications = TenantApplication.objects.count()
        pending_applications = TenantApplication.objects.filter(status='PENDING').count()
        approved_applications = TenantApplication.objects.filter(status='APPROVED').count()
        
        # Maintenance stats
        total_maintenance = MaintenanceRequest.objects.count()
        pending_maintenance = MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        
        # Recent activity
        recent_users = User.objects.order_by('-date_joined')[:5]
        recent_properties = Property.objects.order_by('-created_at')[:5]
        recent_payments = Payment.objects.filter(status='COMPLETED').order_by('-created_at')[:5]
        
        return {
            'total_users': total_users,
            'total_owners': total_owners,
            'total_tenants': total_tenants,
            'pending_verifications': pending_verifications,
            'total_properties': total_properties,
            'verified_properties': verified_properties,
            'pending_properties': pending_properties,
            'total_payments': total_payments,
            'total_revenue': total_revenue,
            'platform_fees': platform_fees,
            'total_applications': total_applications,
            'pending_applications': pending_applications,
            'approved_applications': approved_applications,
            'total_maintenance': total_maintenance,
            'pending_maintenance': pending_maintenance,
            'recent_users': recent_users,
            'recent_properties': recent_properties,
            'recent_payments': recent_payments,
        }
    
    @staticmethod
    def get_property_analytics(property_id):
        """Get detailed analytics for a specific property"""
        property = get_object_or_404(Property, id=property_id)
        
        # Views and engagement
        view_count = property.view_count
        
        # Applications
        applications = TenantApplication.objects.filter(property=property)
        total_applications = applications.count()
        approved_applications = applications.filter(status='APPROVED').count()
        pending_applications = applications.filter(status='PENDING').count()
        rejected_applications = applications.filter(status='REJECTED').count()
        
        # Conversion rate
        conversion_rate = (approved_applications / total_applications * 100) if total_applications > 0 else 0
        
        # Payments
        payments = Payment.objects.filter(property=property, status='COMPLETED')
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        payment_count = payments.count()
        
        # Monthly revenue trend
        monthly_trend = []
        for i in range(6):
            month_start = timezone.now() - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            revenue = Payment.objects.filter(
                property=property,
                status='COMPLETED',
                paid_at__gte=month_start,
                paid_at__lt=month_end
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_trend.append({
                'month': month_start.strftime('%B'),
                'revenue': float(revenue)
            })
        
        # Maintenance
        maintenance = MaintenanceRequest.objects.filter(property=property)
        total_maintenance = maintenance.count()
        pending_maintenance = maintenance.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
        avg_resolution_time = maintenance.filter(
            status='RESOLVED',
            resolved_at__isnull=False
        ).aggregate(
            avg_time=Avg('resolved_at')
        )['avg_time']
        
        # Unit performance (if multi-unit)
        unit_performance = []
        if property.is_multi_unit:
            units = property.units.all()
            for unit in units:
                unit_payments = Payment.objects.filter(
                    property=property,
                    lease__unit=unit,
                    status='COMPLETED'
                )
                unit_performance.append({
                    'unit_number': unit.unit_number,
                    'status': unit.get_status_display(),
                    'rent': unit.get_rental_price(),
                    'payments': unit_payments.count(),
                    'revenue': unit_payments.aggregate(total=Sum('amount'))['total'] or 0,
                })
        
        return {
            'property': property,
            'view_count': view_count,
            'total_applications': total_applications,
            'approved_applications': approved_applications,
            'pending_applications': pending_applications,
            'rejected_applications': rejected_applications,
            'conversion_rate': round(conversion_rate, 1),
            'total_revenue': total_revenue,
            'payment_count': payment_count,
            'monthly_trend': monthly_trend,
            'total_maintenance': total_maintenance,
            'pending_maintenance': pending_maintenance,
            'avg_resolution_time': avg_resolution_time,
            'unit_performance': unit_performance,
        }
    
    @staticmethod
    def generate_report(owner, report_type, date_range, filters=None):
        """Generate a detailed report"""
        from datetime import datetime
        import json
        
        start_date = date_range.get('start')
        end_date = date_range.get('end')
        
        if report_type == 'PROPERTY':
            data = AnalyticsService.generate_property_report(owner, start_date, end_date, filters)
        elif report_type == 'TENANT':
            data = AnalyticsService.generate_tenant_report(owner, start_date, end_date, filters)
        elif report_type == 'FINANCIAL':
            data = AnalyticsService.generate_financial_report(owner, start_date, end_date, filters)
        elif report_type == 'MAINTENANCE':
            data = AnalyticsService.generate_maintenance_report(owner, start_date, end_date, filters)
        else:
            data = {}
        
        return data
    
    @staticmethod
    def generate_property_report(owner, start_date, end_date, filters=None):
        """Generate property performance report"""
        properties = Property.objects.filter(owner=owner)
        
        if filters and filters.get('property_type'):
            properties = properties.filter(property_type=filters['property_type'])
        
        report_data = {
            'title': 'Property Performance Report',
            'generated': timezone.now().isoformat(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None,
            },
            'summary': {
                'total_properties': properties.count(),
                'total_units': sum(p.units.count() if p.is_multi_unit else 1 for p in properties),
                'occupancy_rate': 0,
                'total_revenue': 0,
            },
            'properties': [],
        }
        
        total_units = 0
        occupied_units = 0
        total_revenue = 0
        
        for prop in properties:
            prop_units = prop.units.count() if prop.is_multi_unit else 1
            prop_occupied = prop.units.filter(status='RENTED').count() if prop.is_multi_unit else (1 if prop.availability_status == 'RENTED' else 0)
            
            revenue = Payment.objects.filter(
                property=prop,
                status='COMPLETED',
                created_at__gte=start_date if start_date else timezone.datetime.min,
                created_at__lte=end_date if end_date else timezone.datetime.max
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            report_data['properties'].append({
                'id': str(prop.id),
                'title': prop.title,
                'type': prop.get_property_type_display(),
                'total_units': prop_units,
                'occupied_units': prop_occupied,
                'occupancy': (prop_occupied / prop_units * 100) if prop_units > 0 else 0,
                'revenue': float(revenue),
                'status': prop.get_availability_status_display(),
            })
            
            total_units += prop_units
            occupied_units += prop_occupied
            total_revenue += revenue
        
        report_data['summary']['occupancy_rate'] = (occupied_units / total_units * 100) if total_units > 0 else 0
        report_data['summary']['total_revenue'] = float(total_revenue)
        
        return report_data
    
    @staticmethod
    def generate_tenant_report(owner, start_date, end_date, filters=None):
        """Generate tenant performance report"""
        applications = TenantApplication.objects.filter(
            property__owner=owner,
            created_at__gte=start_date if start_date else timezone.datetime.min,
            created_at__lte=end_date if end_date else timezone.datetime.max
        )
        
        if filters and filters.get('status'):
            applications = applications.filter(status=filters['status'])
        
        report_data = {
            'title': 'Tenant Activity Report',
            'generated': timezone.now().isoformat(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None,
            },
            'summary': {
                'total_applications': applications.count(),
                'pending': applications.filter(status='PENDING').count(),
                'approved': applications.filter(status='APPROVED').count(),
                'rejected': applications.filter(status='REJECTED').count(),
                'cancelled': applications.filter(status='CANCELLED').count(),
            },
            'applications': [],
        }
        
        for app in applications[:100]:  # Limit for performance
            report_data['applications'].append({
                'tenant': app.tenant.get_full_name(),
                'tenant_email': app.tenant.email,
                'property': app.property.title,
                'unit': app.unit.unit_number if app.unit else 'N/A',
                'status': app.get_status_display(),
                'applied': app.created_at.isoformat(),
                'monthly_income': float(app.monthly_income) if app.monthly_income else 0,
                'move_in_date': app.intended_move_in_date.isoformat() if app.intended_move_in_date else None,
            })
        
        return report_data
    
    @staticmethod
    def generate_financial_report(owner, start_date, end_date, filters=None):
        """Generate financial report"""
        payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED',
            created_at__gte=start_date if start_date else timezone.datetime.min,
            created_at__lte=end_date if end_date else timezone.datetime.max
        )
        
        report_data = {
            'title': 'Financial Performance Report',
            'generated': timezone.now().isoformat(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None,
            },
            'summary': {
                'total_payments': payments.count(),
                'total_revenue': float(payments.aggregate(total=Sum('amount'))['total'] or 0),
                'platform_fees': float(payments.aggregate(total=Sum('amount'))['total'] or 0) * 0.03,
                'net_revenue': float(payments.aggregate(total=Sum('amount'))['total'] or 0) * 0.97,
            },
            'payments': [],
            'monthly_breakdown': [],
        }
        
        # Monthly breakdown
        for i in range(6):
            month_start = timezone.now() - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            month_payments = payments.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            )
            report_data['monthly_breakdown'].append({
                'month': month_start.strftime('%B %Y'),
                'payments': month_payments.count(),
                'revenue': float(month_payments.aggregate(total=Sum('amount'))['total'] or 0),
            })
        
        for payment in payments[:50]:
            report_data['payments'].append({
                'id': str(payment.id),
                'tenant': payment.payer.get_full_name(),
                'property': payment.property.title if payment.property else 'N/A',
                'amount': float(payment.amount),
                'type': payment.get_payment_type_display(),
                'date': payment.created_at.isoformat(),
                'method': payment.get_payment_method_display(),
            })
        
        return report_data
    
    @staticmethod
    def generate_maintenance_report(owner, start_date, end_date, filters=None):
        """Generate maintenance report"""
        maintenance = MaintenanceRequest.objects.filter(
            property__owner=owner,
            created_at__gte=start_date if start_date else timezone.datetime.min,
            created_at__lte=end_date if end_date else timezone.datetime.max
        )
        
        if filters and filters.get('category'):
            maintenance = maintenance.filter(category=filters['category'])
        if filters and filters.get('priority'):
            maintenance = maintenance.filter(priority=filters['priority'])
        
        report_data = {
            'title': 'Maintenance Report',
            'generated': timezone.now().isoformat(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None,
            },
            'summary': {
                'total_requests': maintenance.count(),
                'pending': maintenance.filter(status__in=['PENDING', 'IN_PROGRESS']).count(),
                'resolved': maintenance.filter(status='RESOLVED').count(),
                'closed': maintenance.filter(status='CLOSED').count(),
                'cancelled': maintenance.filter(status='CANCELLED').count(),
            },
            'category_breakdown': [],
            'requests': [],
        }
        
        # Category breakdown
        categories = maintenance.values('category').annotate(count=Count('id'))
        for cat in categories:
            report_data['category_breakdown'].append({
                'category': cat['category'],
                'count': cat['count'],
                'label': dict(MaintenanceRequest.CATEGORIES).get(cat['category'], cat['category']),
            })
        
        for req in maintenance[:50]:
            report_data['requests'].append({
                'id': str(req.id),
                'title': req.title,
                'property': req.property.title,
                'unit': req.unit.unit_number if hasattr(req, 'unit') and req.unit else 'N/A',
                'category': req.get_category_display(),
                'priority': req.get_priority_display(),
                'status': req.get_status_display(),
                'created': req.created_at.isoformat(),
                'resolved': req.resolved_at.isoformat() if req.resolved_at else None,
            })
        
        return report_data