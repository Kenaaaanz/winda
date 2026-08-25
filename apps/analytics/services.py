from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from apps.properties.models import Property, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from django.contrib.auth import get_user_model
import calendar
from collections import defaultdict

User = get_user_model()

class AnalyticsService:
    """Comprehensive analytics service for property owners"""
    
    @staticmethod
    def get_owner_dashboard_stats(owner, days=30):
        """Get comprehensive stats for an owner with date filtering"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
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
        
        # Revenue with date filter
        payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED',
            paid_at__date__gte=start_date,
            paid_at__date__lte=end_date
        )
        total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Monthly revenue (last 6 months)
        monthly_revenue = []
        for i in range(6):
            month_start = end_date.replace(day=1) - timedelta(days=30 * i)
            month_start = month_start.replace(day=1)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            revenue = Payment.objects.filter(
                property__owner=owner,
                status='COMPLETED',
                paid_at__date__gte=month_start,
                paid_at__date__lt=month_end
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_revenue.append({
                'month': month_start.strftime('%B'),
                'amount': float(revenue)
            })
        monthly_revenue.reverse()
        
        # Applications
        applications = TenantApplication.objects.filter(
            property__owner=owner,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        total_applications = applications.count()
        pending_applications = applications.filter(status='PENDING').count()
        approved_applications = applications.filter(status='APPROVED').count()
        rejected_applications = applications.filter(status='REJECTED').count()
        
        # Maintenance
        maintenance = MaintenanceRequest.objects.filter(
            property__owner=owner,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        total_maintenance = maintenance.count()
        pending_maintenance = maintenance.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = maintenance.filter(status='RESOLVED').count()
        
        # Tenant stats
        active_leases = Lease.objects.filter(
            property__owner=owner,
            status='ACTIVE'
        )
        
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
                'period': f'{start_date.strftime("%b %d")} - {end_date.strftime("%b %d, %Y")}',
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
            },
            'tenants': {
                'total': active_leases.count(),
                'active_leases': active_leases.count(),
                'expiring_soon': active_leases.filter(
                    end_date__lte=end_date + timedelta(days=30)
                ).count(),
            },
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days,
            }
        }
    
    @staticmethod
    def get_tenant_trends(owner, days=90):
        """Get detailed tenant trends data"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # New tenants over time
        tenant_applications = TenantApplication.objects.filter(
            property__owner=owner,
            created_at__date__gte=start_date
        )
        
        approved_tenants = tenant_applications.filter(status='APPROVED')
        
        # Monthly tenant growth
        monthly_trend = []
        current_date = start_date
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            
            new_tenants = approved_tenants.filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_end
            ).count()
            
            monthly_trend.append({
                'period': month_start.strftime('%b %Y'),
                'new_tenants': new_tenants,
                'total': TenantApplication.objects.filter(
                    property__owner=owner,
                    status='APPROVED',
                    created_at__date__lte=month_end
                ).count()
            })
            
            current_date = month_end + timedelta(days=1)
        
        # Tenant demographics
        tenant_demographics = {
            'by_property': {},
            'by_unit_type': {},
        }
        
        # Group tenants by property
        for prop in Property.objects.filter(owner=owner):
            count = TenantApplication.objects.filter(
                property=prop,
                status='APPROVED'
            ).count()
            if count > 0:
                tenant_demographics['by_property'][prop.title] = count
        
        # Group tenants by unit type (bedrooms)
        for prop in Property.objects.filter(owner=owner):
            if prop.is_multi_unit:
                for unit in prop.units.all():
                    key = f"{unit.bedrooms}br/{unit.bathrooms}ba"
                    count = TenantApplication.objects.filter(
                        unit=unit,
                        status='APPROVED'
                    ).count()
                    if count > 0:
                        tenant_demographics['by_unit_type'][key] = tenant_demographics['by_unit_type'].get(key, 0) + count
        
        return {
            'monthly_trend': monthly_trend,
            'demographics': tenant_demographics,
            'total_tenants': TenantApplication.objects.filter(
                property__owner=owner,
                status='APPROVED'
            ).count(),
            'growth_rate': AnalyticsService._calculate_growth_rate(monthly_trend),
        }
    
    @staticmethod
    def get_payment_trends(owner, days=90):
        """Get detailed payment trends data"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        payments = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED',
            paid_at__date__gte=start_date,
            paid_at__date__lte=end_date
        )
        
        # Monthly payment trends
        monthly_trend = []
        current_date = start_date
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            
            month_payments = payments.filter(
                paid_at__date__gte=month_start,
                paid_at__date__lt=month_end
            )
            
            monthly_trend.append({
                'period': month_start.strftime('%b %Y'),
                'total_amount': float(month_payments.aggregate(total=Sum('amount'))['total'] or 0),
                'count': month_payments.count(),
                'average': float(month_payments.aggregate(avg=Avg('amount'))['avg'] or 0),
            })
            
            current_date = month_end + timedelta(days=1)
        
        # Payment by type
        payment_by_type = {}
        for payment_type, _ in Payment.PAYMENT_TYPES:
            count = payments.filter(payment_type=payment_type).count()
            if count > 0:
                amount = payments.filter(payment_type=payment_type).aggregate(
                    total=Sum('amount')
                )['total'] or 0
                payment_by_type[payment_type] = {
                    'count': count,
                    'amount': float(amount),
                }
        
        # Payment by property
        payment_by_property = {}
        for prop in Property.objects.filter(owner=owner):
            prop_payments = payments.filter(property=prop)
            amount = prop_payments.aggregate(total=Sum('amount'))['total'] or 0
            if amount > 0:
                payment_by_property[prop.title] = {
                    'amount': float(amount),
                    'count': prop_payments.count(),
                }
        
        return {
            'monthly_trend': monthly_trend,
            'by_type': payment_by_type,
            'by_property': payment_by_property,
            'total': {
                'amount': float(payments.aggregate(total=Sum('amount'))['total'] or 0),
                'count': payments.count(),
                'average': float(payments.aggregate(avg=Avg('amount'))['avg'] or 0),
            },
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            }
        }
    
    @staticmethod
    def get_property_trends(owner, days=90):
        """Get detailed property trends data"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        properties = Property.objects.filter(owner=owner)
        
        # Property performance
        property_performance = []
        for prop in properties:
            views = prop.view_count
            applications = prop.applications.count()
            revenue = Payment.objects.filter(
                property=prop,
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            property_performance.append({
                'title': prop.title,
                'views': views,
                'applications': applications,
                'revenue': float(revenue),
                'status': prop.availability_status,
                'is_multi_unit': prop.is_multi_unit,
                'unit_count': prop.units.count() if prop.is_multi_unit else 1,
            })
        
        # Sort by revenue
        property_performance.sort(key=lambda x: x['revenue'], reverse=True)
        
        # Property type distribution
        property_types = {}
        for prop_type, _ in Property.PROPERTY_TYPES:
            count = properties.filter(property_type=prop_type).count()
            if count > 0:
                property_types[prop_type] = count
        
        return {
            'performance': property_performance,
            'property_types': property_types,
            'total_properties': properties.count(),
            'multi_unit_count': properties.filter(is_multi_unit=True).count(),
        }
    
    @staticmethod
    def get_maintenance_trends(owner, days=90):
        """Get detailed maintenance trends data"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        maintenance = MaintenanceRequest.objects.filter(
            property__owner=owner,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Monthly trends
        monthly_trend = []
        current_date = start_date
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            
            month_maintenance = maintenance.filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_end
            )
            
            resolved = month_maintenance.filter(status='RESOLVED').count()
            
            monthly_trend.append({
                'period': month_start.strftime('%b %Y'),
                'total': month_maintenance.count(),
                'resolved': resolved,
                'pending': month_maintenance.count() - resolved,
            })
            
            current_date = month_end + timedelta(days=1)
        
        # By category
        category_stats = {}
        for category, _ in MaintenanceRequest.CATEGORIES:
            count = maintenance.filter(category=category).count()
            if count > 0:
                category_stats[category] = count
        
        # By priority
        priority_stats = {}
        for priority, _ in MaintenanceRequest.PRIORITY_LEVELS:
            count = maintenance.filter(priority=priority).count()
            if count > 0:
                priority_stats[priority] = count
        
        # Average resolution time
        resolved_maintenance = maintenance.filter(status='RESOLVED', resolved_at__isnull=False)
        total_time = 0
        for req in resolved_maintenance:
            if req.resolved_at and req.created_at:
                time_diff = req.resolved_at - req.created_at
                total_time += time_diff.total_seconds() / 3600  # hours
        
        avg_resolution_time = total_time / resolved_maintenance.count() if resolved_maintenance.count() > 0 else 0
        
        return {
            'monthly_trend': monthly_trend,
            'by_category': category_stats,
            'by_priority': priority_stats,
            'total': maintenance.count(),
            'pending': maintenance.filter(
                status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
            ).count(),
            'resolved': maintenance.filter(status='RESOLVED').count(),
            'avg_resolution_time': round(avg_resolution_time, 1),
        }
    
    @staticmethod
    def generate_custom_report(owner, report_config):
        """Generate a custom report based on configuration"""
        report_type = report_config.get('report_type', 'CUSTOM')
        date_from = report_config.get('date_from')
        date_to = report_config.get('date_to')
        metrics = report_config.get('metrics', [])
        filters = report_config.get('filters', {})
        
        data = {}
        
        if 'revenue' in metrics:
            data['revenue'] = AnalyticsService.get_payment_trends(owner)
        if 'tenants' in metrics:
            data['tenants'] = AnalyticsService.get_tenant_trends(owner)
        if 'properties' in metrics:
            data['properties'] = AnalyticsService.get_property_trends(owner)
        if 'maintenance' in metrics:
            data['maintenance'] = AnalyticsService.get_maintenance_trends(owner)
        
        return {
            'title': report_config.get('title', 'Custom Report'),
            'report_type': report_type,
            'generated_at': timezone.now().isoformat(),
            'date_range': {
                'from': date_from,
                'to': date_to,
            },
            'data': data,
            'filters': filters,
        }
    
    @staticmethod
    def _calculate_growth_rate(monthly_trend):
        """Calculate growth rate from monthly trend data"""
        if len(monthly_trend) < 2:
            return 0
        
        first = monthly_trend[0]['total'] if 'total' in monthly_trend[0] else 0
        last = monthly_trend[-1]['total'] if 'total' in monthly_trend[-1] else 0
        
        if first == 0:
            return 100 if last > 0 else 0
        
        return round(((last - first) / first) * 100, 1)