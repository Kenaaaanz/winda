from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, datetime
import json
import csv
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

from apps.payments.models import Payment
from .models import AnalyticsReport, AnalyticsDashboard
from .services import AnalyticsService
from apps.accounts.decorators import owner_required
from apps.properties.models import Property
from apps.tenants.models import TenantApplication


@login_required
def analytics_dashboard(request):
    """Main analytics dashboard"""
    if request.user.is_superuser:
        return admin_analytics_dashboard(request)
    elif request.user.is_owner:
        return owner_analytics_dashboard(request)
    else:
        messages.error(request, 'You do not have access to analytics.')
        return redirect('dashboard')


@login_required
@owner_required
def owner_analytics_dashboard(request):
    """Owner analytics dashboard"""
    owner = request.user.owner_profile
    stats = AnalyticsService.get_owner_dashboard_stats(owner)
    
    # Get property filter
    property_filter = request.GET.get('property')
    if property_filter:
        stats['filtered_property'] = get_object_or_404(Property, id=property_filter, owner=owner)
    
    # Get date range
    date_range = request.GET.get('range', '30')
    days = int(date_range)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Get saved reports
    reports = AnalyticsReport.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'reports': reports,
        'date_range': days,
        'properties': Property.objects.filter(owner=owner),
    }
    
    return render(request, 'analytics/owner_dashboard.html', context)


@login_required
def admin_analytics_dashboard(request):
    """Admin analytics dashboard"""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have access to this page.')
        return redirect('dashboard')
    
    stats = AnalyticsService.get_admin_dashboard_stats()
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'analytics/admin_dashboard.html', context)


@login_required
@owner_required
def property_analytics(request, property_id):
    """Detailed analytics for a specific property"""
    property_obj = get_object_or_404(Property, id=property_id)
    
    # Check permission
    if property_obj.owner != request.user.owner_profile and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this analytics.')
        return redirect('analytics:dashboard')
    
    analytics_data = AnalyticsService.get_property_analytics(property_id)
    
    return render(request, 'analytics/property_analytics.html', analytics_data)


@login_required
@owner_required
def generate_report(request):
    """Generate a custom report"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        title = request.POST.get('title', f'{report_type} Report')
        date_range = json.loads(request.POST.get('date_range', '{}'))
        filters = json.loads(request.POST.get('filters', '{}'))
        format_type = request.POST.get('format', 'PDF')
        
        start_date = None
        end_date = None
        if date_range.get('start'):
            start_date = datetime.fromisoformat(date_range['start'])
        if date_range.get('end'):
            end_date = datetime.fromisoformat(date_range['end'])
        
        # Generate report data
        if request.user.is_superuser:
            # Admin reports (all data)
            data = AnalyticsService.generate_admin_report(report_type, start_date, end_date, filters)
        else:
            owner = request.user.owner_profile
            data = AnalyticsService.generate_report(owner, report_type, {'start': start_date, 'end': end_date}, filters)
        
        # Save report
        report = AnalyticsReport.objects.create(
            user=request.user,
            report_type=report_type,
            title=title,
            description=request.POST.get('description', ''),
            format=format_type,
            filters=filters,
            data=data,
        )
        
        # Generate file
        if format_type == 'PDF':
            file_content = generate_pdf_report(report, data)
            report.file.save(f'{title}_{timezone.now().strftime("%Y%m%d")}.pdf', file_content)
        elif format_type == 'CSV':
            file_content = generate_csv_report(report, data)
            report.file.save(f'{title}_{timezone.now().strftime("%Y%m%d")}.csv', file_content)
        
        report.last_generated = timezone.now()
        report.save()
        
        messages.success(request, 'Report generated successfully!')
        return redirect('analytics:report_detail', report_id=report.id)
    
    return render(request, 'analytics/generate_report.html', {
        'report_types': AnalyticsReport.REPORT_TYPES,
        'properties': Property.objects.filter(owner=request.user.owner_profile) if request.user.is_owner else None,
    })


@login_required
def report_detail(request, report_id):
    """View a saved report"""
    report = get_object_or_404(AnalyticsReport, id=report_id, user=request.user)
    
    if request.user.is_superuser or report.user == request.user:
        return render(request, 'analytics/report_detail.html', {
            'report': report,
        })
    
    messages.error(request, 'You do not have permission to view this report.')
    return redirect('analytics:dashboard')


@login_required
def download_report(request, report_id):
    """Download a report file"""
    report = get_object_or_404(AnalyticsReport, id=report_id, user=request.user)
    
    if not report.file:
        messages.error(request, 'Report file not found.')
        return redirect('analytics:report_detail', report_id=report.id)
    
    response = HttpResponse(report.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{report.file.name}"'
    return response


@login_required
def export_data(request):
    """Export raw data for selected metrics"""
    if request.method == 'POST':
        metrics = request.POST.getlist('metrics')
        date_range = json.loads(request.POST.get('date_range', '{}'))
        
        start_date = None
        end_date = None
        if date_range.get('start'):
            start_date = datetime.fromisoformat(date_range['start'])
        if date_range.get('end'):
            end_date = datetime.fromisoformat(date_range['end'])
        
        # Get data based on metrics
        data = {}
        for metric in metrics:
            if metric == 'payments':
                payments = Payment.objects.filter(
                    property__owner=request.user.owner_profile if request.user.is_owner else None,
                    status='COMPLETED'
                )
                data['payments'] = [
                    {
                        'date': p.created_at,
                        'amount': float(p.amount),
                        'type': p.get_payment_type_display(),
                        'tenant': p.payer.get_full_name(),
                    }
                    for p in payments
                ]
            elif metric == 'applications':
                apps = TenantApplication.objects.filter(
                    property__owner=request.user.owner_profile if request.user.is_owner else None
                )
                data['applications'] = [
                    {
                        'date': a.created_at,
                        'tenant': a.tenant.get_full_name(),
                        'property': a.property.title,
                        'status': a.get_status_display(),
                    }
                    for a in apps
                ]
            # Add more metrics as needed
        
        # Generate CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export_data.csv"'
        
        writer = csv.writer(response)
        for metric_name, rows in data.items():
            if rows:
                writer.writerow([metric_name.upper()])
                if rows:
                    writer.writerow(rows[0].keys())
                    for row in rows:
                        writer.writerow(row.values())
                writer.writerow([])
        
        return response
    
    return redirect('analytics:dashboard')


# Helper functions for report generation

def generate_pdf_report(report, data):
    """Generate PDF report"""
    from reportlab.lib.utils import ImageReader
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2563EB'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    story.append(Paragraph(report.title, title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Summary
    if 'summary' in data:
        story.append(Paragraph('Summary', styles['Heading2']))
        summary_data = [['Metric', 'Value']]
        for key, value in data['summary'].items():
            if isinstance(value, (int, float)):
                if 'revenue' in key or 'fee' in key:
                    summary_data.append([key.replace('_', ' ').title(), f'${value:,.2f}'])
                else:
                    summary_data.append([key.replace('_', ' ').title(), f'{value:,}'])
            elif isinstance(value, str):
                summary_data.append([key.replace('_', ' ').title(), value])
        
        t = Table(summary_data, colWidths=[3*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25*inch))
    
    # Generated date
    story.append(Paragraph(f'Generated: {timezone.now().strftime("%B %d, %Y %H:%M")}', styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_csv_report(report, data):
    """Generate CSV report"""
    import io
    import csv
    
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # Title
    writer.writerow([report.title])
    writer.writerow([f'Generated: {timezone.now().strftime("%B %d, %Y %H:%M")}'])
    writer.writerow([])
    
    # Data
    if 'summary' in data:
        writer.writerow(['SUMMARY'])
        for key, value in data['summary'].items():
            writer.writerow([key.replace('_', ' ').title(), value])
        writer.writerow([])
    
    # Additional data sections
    for key, value in data.items():
        if key != 'summary' and isinstance(value, list) and value:
            writer.writerow([key.replace('_', ' ').title().upper()])
            if isinstance(value[0], dict):
                writer.writerow(value[0].keys())
                for item in value:
                    writer.writerow(item.values())
            writer.writerow([])
    
    return io.BytesIO(buffer.getvalue().encode('utf-8'))