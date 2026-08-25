from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
import json
import csv
from decimal import Decimal

from apps.maintenance.models import MaintenanceRequest
from apps.payments.models import Payment
from apps.tenants.models import TenantApplication

from .services import AnalyticsService
from .models import AnalyticsEvent, SavedReport, ReportExport
from ..accounts.decorators import owner_required
from ..properties.models import Property


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard - handles both owner and admin views"""
    
    if request.user.is_superuser:
        # Admin view
        stats = AnalyticsService.get_platform_stats()
        
        # Prepare chart data
        chart_data = {
            'revenue_labels': [item['month'] for item in stats['revenue']['monthly']],
            'revenue_data': [float(item['amount']) for item in stats['revenue']['monthly']],
        }
        
        return render(request, 'analytics/dashboard.html', {
            'stats': stats,
            'chart_data': chart_data,
            'is_admin': True,
            'days': 30,
        })
    
    elif request.user.user_type == 'HOUSE_OWNER':
        # Owner view
        owner = request.user.owner_profile
        days = int(request.GET.get('days', 30))
        
        stats = AnalyticsService.get_owner_dashboard_stats(owner, days)
        tenant_trends = AnalyticsService.get_tenant_trends(owner, min(days, 90))
        payment_trends = AnalyticsService.get_payment_trends(owner, min(days, 90))
        maintenance_trends = AnalyticsService.get_maintenance_trends(owner, min(days, 90))
        
        # Prepare chart data for templates
        chart_data = {
            'revenue_labels': [item['month'] for item in stats['revenue']['monthly']],
            'revenue_data': [float(item['amount']) for item in stats['revenue']['monthly']],
            'tenant_labels': [item['period'] for item in tenant_trends['monthly_trend']],
            'tenant_data': [item['new_tenants'] for item in tenant_trends['monthly_trend']],
        }
        
        return render(request, 'analytics/dashboard.html', {
            'stats': stats,
            'chart_data': chart_data,
            'tenant_trends': tenant_trends,
            'payment_trends': payment_trends,
            'maintenance_trends': maintenance_trends,
            'days': days,
            'is_admin': False,
            'saved_reports': SavedReport.objects.filter(owner=owner, is_active=True)[:5],
        })
    else:
        messages.error(request, 'You do not have access to analytics.')
        return redirect('dashboard')


@login_required
@owner_required
def property_analytics(request, property_id):
    """Analytics for a specific property"""
    property_obj = get_object_or_404(Property, id=property_id)
    
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
@owner_required
def tenant_trends(request):
    """Tenant trends view"""
    owner = request.user.owner_profile
    days = int(request.GET.get('days', 90))
    data = AnalyticsService.get_tenant_trends(owner, days)
    
    # Prepare chart data
    chart_data = {
        'labels': [item['period'] for item in data['monthly_trend']],
        'new_tenants': [item['new_tenants'] for item in data['monthly_trend']],
        'total_tenants': [item['total'] for item in data['monthly_trend']],
    }
    
    return render(request, 'analytics/tenant_trends.html', {
        'data': data,
        'chart_data': chart_data,
        'days': days,
    })


@login_required
@owner_required
def payment_trends(request):
    """Payment trends view"""
    owner = request.user.owner_profile
    days = int(request.GET.get('days', 90))
    data = AnalyticsService.get_payment_trends(owner, days)
    
    # Prepare chart data
    chart_data = {
        'labels': [item['period'] for item in data['monthly_trend']],
        'amounts': [item['total_amount'] for item in data['monthly_trend']],
        'counts': [item['count'] for item in data['monthly_trend']],
        'averages': [item['average'] for item in data['monthly_trend']],
    }
    
    # Prepare pie chart data for payment types
    pie_data = {
        'labels': list(data['by_type'].keys()),
        'values': [item['amount'] for item in data['by_type'].values()],
    }
    
    return render(request, 'analytics/payment_trends.html', {
        'data': data,
        'chart_data': chart_data,
        'pie_data': pie_data,
        'days': days,
    })


@login_required
@owner_required
def maintenance_analytics(request):
    """Maintenance analytics view"""
    owner = request.user.owner_profile
    days = int(request.GET.get('days', 90))
    data = AnalyticsService.get_maintenance_trends(owner, days)
    
    # Prepare chart data
    chart_data = {
        'labels': [item['period'] for item in data['monthly_trend']],
        'total': [item['total'] for item in data['monthly_trend']],
        'resolved': [item['resolved'] for item in data['monthly_trend']],
        'pending': [item['pending'] for item in data['monthly_trend']],
    }
    
    # Category data for pie chart
    category_data = {
        'labels': list(data['by_category'].keys()),
        'values': list(data['by_category'].values()),
    }
    
    # Priority data for bar chart
    priority_data = {
        'labels': list(data['by_priority'].keys()),
        'values': list(data['by_priority'].values()),
    }
    
    return render(request, 'analytics/maintenance_analytics.html', {
        'data': data,
        'chart_data': chart_data,
        'category_data': category_data,
        'priority_data': priority_data,
        'days': days,
    })


@login_required
@owner_required
def custom_report(request):
    """Create and manage custom reports"""
    owner = request.user.owner_profile
    
    if request.method == 'POST':
        report_config = {
            'title': request.POST.get('title', 'Custom Report'),
            'report_type': request.POST.get('report_type', 'CUSTOM'),
            'date_from': request.POST.get('date_from'),
            'date_to': request.POST.get('date_to'),
            'metrics': request.POST.getlist('metrics'),
            'filters': json.loads(request.POST.get('filters', '{}')),
        }
        
        # Validate dates
        if not report_config['date_from'] or not report_config['date_to']:
            messages.error(request, 'Please select both start and end dates.')
            return redirect('analytics:custom_report')
        
        # Generate report data
        report_data = AnalyticsService.generate_custom_report(owner, report_config)
        
        # Save report
        saved_report = SavedReport.objects.create(
            owner=owner,
            title=report_config['title'],
            report_type=report_config['report_type'],
            date_from=report_config['date_from'],
            date_to=report_config['date_to'],
            metrics=report_config['metrics'],
            filters=report_config['filters'],
            chart_type=request.POST.get('chart_type', 'line'),
        )
        
        messages.success(request, 'Report generated successfully!')
        return redirect('analytics:view_report', report_id=saved_report.id)
    
    # Get properties for filtering
    properties = Property.objects.filter(owner=owner)
    
    context = {
        'properties': properties,
        'metrics_choices': [
            ('revenue', 'Revenue'),
            ('tenants', 'Tenants'),
            ('properties', 'Properties'),
            ('maintenance', 'Maintenance'),
        ],
        'saved_reports': SavedReport.objects.filter(owner=owner, is_active=True),
    }
    return render(request, 'analytics/custom_report.html', context)


@login_required
@owner_required
def view_report(request, report_id):
    """View a saved report"""
    report = get_object_or_404(SavedReport, id=report_id, owner=request.user.owner_profile)
    
    # Regenerate report data
    report_config = {
        'title': report.title,
        'report_type': report.report_type,
        'date_from': report.date_from.isoformat(),
        'date_to': report.date_to.isoformat(),
        'metrics': report.metrics,
        'filters': report.filters,
    }
    
    report_data = AnalyticsService.generate_custom_report(
        request.user.owner_profile,
        report_config
    )
    
    # Prepare chart data based on metrics
    chart_data = {}
    for metric, data in report_data['data'].items():
        if metric == 'revenue' and 'monthly_trend' in data:
            chart_data['revenue'] = {
                'labels': [item['period'] for item in data['monthly_trend']],
                'data': [item['total_amount'] for item in data['monthly_trend']],
            }
        elif metric == 'tenants' and 'monthly_trend' in data:
            chart_data['tenants'] = {
                'labels': [item['period'] for item in data['monthly_trend']],
                'new_tenants': [item['new_tenants'] for item in data['monthly_trend']],
                'total_tenants': [item['total'] for item in data['monthly_trend']],
            }
        elif metric == 'maintenance' and 'monthly_trend' in data:
            chart_data['maintenance'] = {
                'labels': [item['period'] for item in data['monthly_trend']],
                'total': [item['total'] for item in data['monthly_trend']],
                'resolved': [item['resolved'] for item in data['monthly_trend']],
            }
    
    context = {
        'report': report,
        'data': report_data,
        'chart_data': chart_data,
        'chart_type': report.chart_type,
    }
    return render(request, 'analytics/view_report.html', context)


@login_required
@owner_required
def export_report(request, report_id):
    """Export report as CSV"""
    report = get_object_or_404(SavedReport, id=report_id, owner=request.user.owner_profile)
    format_type = request.GET.get('format', 'CSV')
    
    # Generate report data
    report_config = {
        'title': report.title,
        'report_type': report.report_type,
        'date_from': report.date_from.isoformat(),
        'date_to': report.date_to.isoformat(),
        'metrics': report.metrics,
        'filters': report.filters,
    }
    
    report_data = AnalyticsService.generate_custom_report(
        request.user.owner_profile,
        report_config
    )
    
    # Create CSV export
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report.title.replace(" ", "_")}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([f'Report: {report.title}'])
    writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M")}'])
    writer.writerow([f'Date Range: {report.date_from} to {report.date_to}'])
    writer.writerow([])
    
    # Write data for each metric
    for metric, data in report_data['data'].items():
        writer.writerow([f'=== {metric.upper()} ==='])
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        # Write table headers
                        headers = list(value[0].keys())
                        writer.writerow([f'{key}:'] + headers)
                        # Write rows
                        for row in value:
                            writer.writerow([f''] + [str(row.get(h, '')) for h in headers])
                    else:
                        writer.writerow([f'{key}:', str(value)])
                elif isinstance(value, dict):
                    # For simple dicts like by_property
                    writer.writerow([f'{key}:'])
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict):
                            writer.writerow([f'  {sub_key}:', json.dumps(sub_value)])
                        else:
                            writer.writerow([f'  {sub_key}:', str(sub_value)])
                else:
                    writer.writerow([f'{key}:', str(value)])
        writer.writerow([])
    
    # Save export record
    ReportExport.objects.create(
        owner=request.user.owner_profile,
        saved_report=report,
        title=report.title,
        format=format_type,
        data=report_data,
    )
    
    return response


@login_required
@owner_required
def schedule_report(request, report_id):
    """Schedule a report for recurring generation"""
    report = get_object_or_404(SavedReport, id=report_id, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        frequency = request.POST.get('frequency', 'WEEKLY')
        report.is_scheduled = True
        report.schedule_frequency = frequency
        report.save()
        
        messages.success(request, f'Report scheduled {frequency.lower()}.')
        return redirect('analytics:view_report', report_id=report.id)
    
    return render(request, 'analytics/schedule_report.html', {
        'report': report,
    })


@login_required
def analytics_api(request):
    """API endpoint for analytics data"""
    if not request.user.is_superuser and request.user.user_type != 'HOUSE_OWNER':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    data_type = request.GET.get('type', 'dashboard')
    days = int(request.GET.get('days', 30))
    
    if request.user.user_type == 'HOUSE_OWNER':
        owner = request.user.owner_profile
        
        if data_type == 'revenue':
            data = AnalyticsService.get_payment_trends(owner, days)
        elif data_type == 'applications':
            data = {
                'total': TenantApplication.objects.filter(property__owner=owner).count(),
                'pending': TenantApplication.objects.filter(property__owner=owner, status='PENDING').count(),
                'approved': TenantApplication.objects.filter(property__owner=owner, status='APPROVED').count(),
                'rejected': TenantApplication.objects.filter(property__owner=owner, status='REJECTED').count(),
            }
        elif data_type == 'maintenance':
            data = AnalyticsService.get_maintenance_trends(owner, days)
        elif data_type == 'tenants':
            data = AnalyticsService.get_tenant_trends(owner, days)
        else:
            data = AnalyticsService.get_owner_dashboard_stats(owner, days)
    else:
        # Admin API
        if data_type == 'revenue':
            data = AnalyticsService.get_payment_trends(None, days)
        else:
            data = AnalyticsService.get_platform_stats()
    
    return JsonResponse(data, safe=False)


@login_required
def export_analytics(request):
    """Export analytics data as CSV"""
    if not request.user.is_superuser and request.user.user_type != 'HOUSE_OWNER':
        messages.error(request, 'You do not have permission to export analytics.')
        return redirect('dashboard')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Views', 'Applications', 'Revenue', 'Maintenance'])
    
    # Get data for the last 30 days
    today = timezone.now().date()
    for i in range(30):
        date = today - timedelta(days=i)
        
        if request.user.user_type == 'HOUSE_OWNER':
            owner = request.user.owner_profile
            views = AnalyticsEvent.objects.filter(
                property__owner=owner,
                event_type='PROPERTY_VIEW',
                created_at__date=date
            ).count()
            applications = TenantApplication.objects.filter(
                property__owner=owner,
                created_at__date=date
            ).count()
            revenue = Payment.objects.filter(
                property__owner=owner,
                status='COMPLETED',
                paid_at__date=date
            ).aggregate(total=Sum('amount'))['total'] or 0
            maintenance = MaintenanceRequest.objects.filter(
                property__owner=owner,
                created_at__date=date
            ).count()
        else:
            views = AnalyticsEvent.objects.filter(
                event_type='PROPERTY_VIEW',
                created_at__date=date
            ).count()
            applications = TenantApplication.objects.filter(
                created_at__date=date
            ).count()
            revenue = Payment.objects.filter(
                status='COMPLETED',
                paid_at__date=date
            ).aggregate(total=Sum('amount'))['total'] or 0
            maintenance = MaintenanceRequest.objects.filter(
                created_at__date=date
            ).count()
        
        writer.writerow([
            date.strftime('%Y-%m-%d'),
            views,
            applications,
            float(revenue),
            maintenance
        ])
    
    return response