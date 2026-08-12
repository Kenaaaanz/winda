from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta
import json

from .models import PageView, UserActivity, DailyAnalyticsReport
from ..accounts.decorators import user_type_required
from ..properties.models import Property
from ..payments.models import Payment
from ..tenants.models import TenantApplication


@login_required
def analytics_dashboard(request):
    """Analytics dashboard"""
    if request.user.is_superuser:
        return admin_analytics(request)
    elif request.user.user_type == 'HOUSE_OWNER':
        return owner_analytics(request)
    else:
        messages.error(request, 'You do not have access to analytics.')
        return redirect('dashboard')


def admin_analytics(request):
    """Admin analytics dashboard"""
    today = timezone.now()
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    last_year = today - timedelta(days=365)
    
    # General stats
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    total_users = User.objects.filter(is_active=True).count()
    active_users = UserActivity.objects.filter(
        created_at__gte=last_week
    ).values('user').distinct().count()
    new_users = User.objects.filter(date_joined__gte=last_month).count()
    
    # Property stats
    total_properties = Property.objects.count()
    new_properties = Property.objects.filter(created_at__gte=last_month).count()
    available_properties = Property.objects.filter(availability_status='AVAILABLE').count()
    rented_properties = Property.objects.filter(availability_status='RENTED').count()
    
    # Payment stats
    total_revenue = Payment.objects.filter(
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_revenue = Payment.objects.filter(
        status='COMPLETED',
        paid_at__gte=last_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Application stats
    total_applications = TenantApplication.objects.count()
    pending_applications = TenantApplication.objects.filter(status='PENDING').count()
    approved_applications = TenantApplication.objects.filter(status='APPROVED').count()
    
    # Page views
    total_views = PageView.objects.count()
    unique_visitors = PageView.objects.values('session_id').distinct().count()
    
    # Daily visits chart data (last 30 days)
    daily_visits = []
    for i in range(30):
        date = today - timedelta(days=i)
        count = PageView.objects.filter(
            created_at__date=date
        ).count()
        daily_visits.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'new_users': new_users,
        'total_properties': total_properties,
        'new_properties': new_properties,
        'available_properties': available_properties,
        'rented_properties': rented_properties,
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'total_views': total_views,
        'unique_visitors': unique_visitors,
        'daily_visits': daily_visits,
        'is_admin': True,
    }
    
    return render(request, 'analytics/admin_dashboard.html', context)


@login_required
@user_type_required('HOUSE_OWNER')
def owner_analytics(request):
    """Owner analytics dashboard"""
    owner = request.user.owner_profile
    today = timezone.now()
    last_month = today - timedelta(days=30)
    last_year = today - timedelta(days=365)
    
    # Property statistics
    properties = Property.objects.filter(owner=owner)
    total_properties = properties.count()
    occupied = properties.filter(availability_status='RENTED').count()
    available = properties.filter(availability_status='AVAILABLE').count()
    under_maintenance = properties.filter(availability_status='UNDER_MAINTENANCE').count()
    
    occupancy_rate = (occupied / total_properties * 100) if total_properties > 0 else 0
    
    # Revenue
    total_revenue = Payment.objects.filter(
        property__owner=owner,
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_revenue = Payment.objects.filter(
        property__owner=owner,
        status='COMPLETED',
        paid_at__gte=last_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    yearly_revenue = Payment.objects.filter(
        property__owner=owner,
        status='COMPLETED',
        paid_at__gte=last_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Applications
    applications = TenantApplication.objects.filter(property__owner=owner)
    total_applications = applications.count()
    pending_applications = applications.filter(status='PENDING').count()
    approved_applications = applications.filter(status='APPROVED').count()
    rejected_applications = applications.filter(status='REJECTED').count()
    
    # Maintenance
    from ..maintenance.models import MaintenanceRequest
    maintenance = MaintenanceRequest.objects.filter(property__owner=owner)
    pending_maintenance = maintenance.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
    
    # Property performance
    property_performance = []
    for prop in properties[:5]:
        views = prop.view_count
        inquiries = prop.applications.count()
        favorites = prop.favorites.count()
        property_performance.append({
            'title': prop.title,
            'views': views,
            'inquiries': inquiries,
            'favorites': favorites,
            'occupancy': 'Rented' if prop.availability_status == 'RENTED' else 'Available'
        })
    
    # Monthly revenue chart (last 6 months)
    monthly_chart = []
    for i in range(6):
        month_start = today - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        revenue = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED',
            paid_at__gte=month_start,
            paid_at__lt=month_end
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_chart.append({
            'month': month_start.strftime('%B'),
            'revenue': float(revenue)
        })
    
    context = {
        'total_properties': total_properties,
        'occupied': occupied,
        'available': available,
        'under_maintenance': under_maintenance,
        'occupancy_rate': round(occupancy_rate, 1),
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'yearly_revenue': yearly_revenue,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'pending_maintenance': pending_maintenance,
        'property_performance': property_performance,
        'monthly_chart': monthly_chart,
        'is_owner': True,
    }
    
    return render(request, 'analytics/owner_dashboard.html', context)


@login_required
def property_analytics(request, property_id):
    """Analytics for a specific property"""
    property_obj = get_object_or_404(Property, id=property_id)
    
    # Check permission
    if property_obj.owner.user != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this analytics.')
        return redirect('dashboard')
    
    # Property statistics
    views = property_obj.view_count
    favorites = property_obj.favorites.count()
    inquiries = property_obj.applications.count()
    
    # Application stats
    applications = property_obj.applications
    pending = applications.filter(status='PENDING').count()
    approved = applications.filter(status='APPROVED').count()
    rejected = applications.filter(status='REJECTED').count()
    
    # Payment stats
    payments = Payment.objects.filter(property=property_obj, status='COMPLETED')
    total_rent = payments.aggregate(total=Sum('amount'))['total'] or 0
    
    # Monthly view trends
    today = timezone.now()
    monthly_views = []
    for i in range(6):
        month_start = today - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        count = PageView.objects.filter(
            path__contains=f'/property/{property_obj.id}',
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        monthly_views.append({
            'month': month_start.strftime('%B'),
            'views': count
        })
    
    context = {
        'property': property_obj,
        'views': views,
        'favorites': favorites,
        'inquiries': inquiries,
        'pending_applications': pending,
        'approved_applications': approved,
        'rejected_applications': rejected,
        'total_rent': total_rent,
        'monthly_views': monthly_views,
    }
    
    return render(request, 'analytics/property_analytics.html', context)


@login_required
def get_visit_data(request):
    """API endpoint for visit data"""
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    visits = PageView.objects.filter(
        created_at__gte=start_date
    ).extra({
        'date': "DATE_TRUNC('day', created_at)"
    }).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    return JsonResponse(list(visits), safe=False)


@login_required
def get_revenue_data(request):
    """API endpoint for revenue data"""
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    if request.user.user_type == 'HOUSE_OWNER':
        owner = request.user.owner_profile
        revenues = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED',
            paid_at__gte=start_date
        ).extra({
            'date': "DATE_TRUNC('day', paid_at)"
        }).values('date').annotate(
            total=Sum('amount')
        ).order_by('date')
    else:
        revenues = Payment.objects.filter(
            status='COMPLETED',
            paid_at__gte=start_date
        ).extra({
            'date': "DATE_TRUNC('day', paid_at)"
        }).values('date').annotate(
            total=Sum('amount')
        ).order_by('date')
    
    return JsonResponse(list(revenues), safe=False)


@login_required
def export_analytics(request):
    """Export analytics data as CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Views', 'Revenue', 'Applications'])
    
    # Get data
    today = timezone.now()
    for i in range(30):
        date = today - timedelta(days=i)
        views = PageView.objects.filter(created_at__date=date).count()
        revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date=date
        ).aggregate(total=Sum('amount'))['total'] or 0
        applications = TenantApplication.objects.filter(created_at__date=date).count()
        
        writer.writerow([date.strftime('%Y-%m-%d'), views, float(revenue), applications])
    
    return response