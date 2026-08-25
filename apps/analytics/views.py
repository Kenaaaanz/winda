from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
import json

from .services import AnalyticsService
from ..accounts.decorators import owner_required
from ..properties.models import Property


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard"""
    if request.user.is_superuser:
        return admin_analytics(request)
    elif request.user.user_type == 'HOUSE_OWNER':
        return owner_analytics(request)
    else:
        messages.error(request, 'You do not have access to analytics.')
        return redirect('dashboard')


@login_required
@owner_required
def owner_analytics(request):
    """Owner analytics dashboard"""
    owner = request.user.owner_profile
    stats = AnalyticsService.get_owner_dashboard_stats(owner)
    
    # Prepare chart data for templates
    chart_data = {
        'revenue_labels': [item['month'] for item in stats['revenue']['monthly']],
        'revenue_data': [float(item['amount']) for item in stats['revenue']['monthly']],
        'application_labels': [item['month'] for item in stats['applications']['trend']],
        'application_data': [item['count'] for item in stats['applications']['trend']],
    }
    
    context = {
        'stats': stats,
        'chart_data': chart_data,
        'user_type': 'owner',
        'property_count': stats['properties']['total'],
    }
    return render(request, 'analytics/owner_dashboard.html', context)

@login_required
def admin_analytics(request):
    """Admin analytics dashboard"""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('dashboard')
    
    stats = AnalyticsService.get_platform_stats()
    
    # Prepare chart data for templates
    chart_data = {
        'revenue_labels': [item['month'] for item in stats['revenue']['monthly']],
        'revenue_data': [float(item['amount']) for item in stats['revenue']['monthly']],
    }
    
    context = {
        'stats': stats,
        'chart_data': chart_data,
        'user_type': 'admin',
    }
    return render(request, 'analytics/admin_dashboard.html', context)

@login_required
@owner_required
def property_analytics(request, property_id):
    """Analytics for a specific property"""
    property_obj = get_object_or_404(Property, id=property_id)
    
    # Check ownership
    if property_obj.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to view this analytics.')
        return redirect('analytics:dashboard')
    
    stats = AnalyticsService.get_property_analytics(property_obj)
    unit_performance = AnalyticsService.get_unit_performance(property_obj)
    
    context = {
        'property': property_obj,
        'stats': stats,
        'unit_performance': unit_performance,
    }
    return render(request, 'analytics/property_analytics.html', context)


@login_required
def analytics_api(request):
    """API endpoint for analytics data"""
    if not request.user.is_superuser and request.user.user_type != 'HOUSE_OWNER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    data_type = request.GET.get('type', 'dashboard')
    days = int(request.GET.get('days', 30))
    
    if data_type == 'revenue':
        data = AnalyticsService.get_revenue_data(request.user, days)
    elif data_type == 'applications':
        data = AnalyticsService.get_application_data(request.user, days)
    elif data_type == 'maintenance':
        data = AnalyticsService.get_maintenance_data(request.user, days)
    else:
        data = {'error': 'Invalid data type'}
    
    return JsonResponse(data)


@login_required
def export_analytics(request):
    """Export analytics data as CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Views', 'Applications', 'Revenue', 'Maintenance'])
    
    # Get data for the last 30 days
    today = timezone.now().date()
    for i in range(30):
        date = today - timedelta(days=i)
        # Calculate stats for this date
        writer.writerow([
            date.strftime('%Y-%m-%d'),
            0,  # views
            0,  # applications
            0,  # revenue
            0,  # maintenance
        ])
    
    return response