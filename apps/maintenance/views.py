from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q

from .models import MaintenanceRequest, MaintenanceTask, MaintenanceChecklist
from .forms import MaintenanceRequestForm, MaintenanceTaskForm
from ..accounts.decorators import tenant_required, owner_required
from ..properties.models import Property
from ..notifications.models import Notification


@login_required
def maintenance_list(request):
    """List maintenance requests"""
    if request.user.user_type == 'HOUSE_OWNER' or request.user.user_type == 'CARETAKER':
        # Owner/Caretaker sees requests for their properties
        if request.user.user_type == 'HOUSE_OWNER':
            requests = MaintenanceRequest.objects.filter(
                property__owner=request.user.owner_profile
            )
        else:
            # Caretaker
            requests = MaintenanceRequest.objects.filter(
                property__owner=request.user.caretaker_profile.owner
            )
    else:
        # Tenant sees their own requests
        requests = MaintenanceRequest.objects.filter(tenant=request.user)
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        requests = requests.filter(status=status_filter)
    
    # Filter by priority
    priority_filter = request.GET.get('priority')
    if priority_filter and priority_filter != 'all':
        requests = requests.filter(priority=priority_filter)
    
    paginator = Paginator(requests, 10)
    page = request.GET.get('page')
    try:
        requests_page = paginator.page(page)
    except PageNotAnInteger:
        requests_page = paginator.page(1)
    except EmptyPage:
        requests_page = paginator.page(paginator.num_pages)
    
    return render(request, 'maintenance/list.html', {
        'requests': requests_page,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': MaintenanceRequest.STATUS_CHOICES,
        'priority_choices': MaintenanceRequest.PRIORITY_LEVELS,
    })


@login_required
@tenant_required
def maintenance_create(request):
    """Create a new maintenance request"""
    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST, request.FILES)
        if form.is_valid():
            request_obj = form.save(commit=False)
            request_obj.tenant = request.user
            request_obj.save()
            
            # Handle images
            images = request.FILES.getlist('images')
            if images:
                image_urls = []
                for img in images:
                    # Save image and get URL
                    image_urls.append(img.name)  # Simplified - you'd save properly
                request_obj.images = image_urls
                request_obj.save()
            
            # Create notification for owner
            owner = request_obj.property.owner.user
            Notification.objects.create(
                user=owner,
                notification_type='MAINTENANCE',
                title='New Maintenance Request',
                message=f'{request.user.get_full_name()} reported: {request_obj.title}',
                related_object_type='maintenance',
                related_object_id=str(request_obj.id),
                data={
                    'property_id': str(request_obj.property.id),
                    'tenant_id': str(request.user.id)
                }
            )
            
            messages.success(request, 'Maintenance request created successfully!')
            return redirect('maintenance:detail', pk=request_obj.pk)
    else:
        # Pre-fill property if provided
        property_id = request.GET.get('property_id')
        if property_id:
            property = get_object_or_404(Property, id=property_id)
            form = MaintenanceRequestForm(initial={'property': property})
        else:
            form = MaintenanceRequestForm()
    
    return render(request, 'maintenance/create.html', {
        'form': form,
    })


@login_required
def maintenance_detail(request, pk):
    """View maintenance request details"""
    request_obj = get_object_or_404(MaintenanceRequest, pk=pk)
    
    # Check permission
    if request_obj.tenant != request.user:
        if request.user.user_type == 'HOUSE_OWNER':
            if request_obj.property.owner != request.user.owner_profile:
                messages.error(request, 'You do not have permission to view this request.')
                return redirect('maintenance:list')
        elif request.user.user_type == 'CARETAKER':
            if request_obj.property.owner != request.user.caretaker_profile.owner:
                messages.error(request, 'You do not have permission to view this request.')
                return redirect('maintenance:list')
        else:
            messages.error(request, 'You do not have permission to view this request.')
            return redirect('maintenance:list')
    
    # Handle status update for owners/caretakers
    if request.method == 'POST' and (request.user.user_type == 'HOUSE_OWNER' or request.user.user_type == 'CARETAKER'):
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if status in dict(MaintenanceRequest.STATUS_CHOICES):
            request_obj.status = status
            if status == 'RESOLVED':
                request_obj.resolved_at = timezone.now()
                if notes:
                    request_obj.resolution_notes = notes
            elif status == 'CLOSED':
                request_obj.closed_at = timezone.now()
            request_obj.save()
            
            # Notify tenant
            Notification.objects.create(
                user=request_obj.tenant,
                notification_type='MAINTENANCE',
                title='Maintenance Request Updated',
                message=f'Your request "{request_obj.title}" is now {status.lower()}.',
                related_object_type='maintenance',
                related_object_id=str(request_obj.id)
            )
            
            messages.success(request, 'Request status updated successfully!')
            return redirect('maintenance:detail', pk=request_obj.pk)
    
    return render(request, 'maintenance/detail.html', {
        'request_obj': request_obj,
        'is_owner': request.user.user_type == 'HOUSE_OWNER',
        'is_caretaker': request.user.user_type == 'CARETAKER',
    })


@login_required
@owner_required
def maintenance_assign(request, pk):
    """Assign maintenance request to someone"""
    request_obj = get_object_or_404(MaintenanceRequest, pk=pk)
    
    if request_obj.property.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to assign this request.')
        return redirect('maintenance:list')
    
    if request.method == 'POST':
        user_id = request.POST.get('assigned_to')
        if user_id:
            assigned_user = get_object_or_404(User, id=user_id)
            request_obj.assign(assigned_user)
            
            Notification.objects.create(
                user=assigned_user,
                notification_type='MAINTENANCE',
                title='Maintenance Request Assigned',
                message=f'You have been assigned to: {request_obj.title}',
                related_object_type='maintenance',
                related_object_id=str(request_obj.id)
            )
            
            messages.success(request, f'Request assigned to {assigned_user.get_full_name()}')
        return redirect('maintenance:detail', pk=request_obj.pk)
    
    # Get caretakers and other staff
    staff = User.objects.filter(
        user_type__in=['CARETAKER']
    ).exclude(id=request.user.id)
    
    return render(request, 'maintenance/assign.html', {
        'request_obj': request_obj,
        'staff': staff,
    })


@login_required
@owner_required
def maintenance_report(request):
    """Generate maintenance report"""
    from django.db.models import Count
    from datetime import timedelta
    
    owner = request.user.owner_profile
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    requests = MaintenanceRequest.objects.filter(property__owner=owner)
    
    if start_date:
        requests = requests.filter(created_at__gte=start_date)
    if end_date:
        requests = requests.filter(created_at__lte=end_date)
    
    # Statistics
    total_requests = requests.count()
    pending = requests.filter(status='PENDING').count()
    in_progress = requests.filter(status='IN_PROGRESS').count()
    resolved = requests.filter(status='RESOLVED').count()
    closed = requests.filter(status='CLOSED').count()
    
    # Priority breakdown
    priority_stats = requests.values('priority').annotate(count=Count('id'))
    
    # Category breakdown
    category_stats = requests.values('category').annotate(count=Count('id'))
    
    # Monthly trends
    monthly_stats = []
    for i in range(6):
        month_start = timezone.now() - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        count = requests.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        monthly_stats.append({
            'month': month_start.strftime('%B %Y'),
            'count': count
        })
    
    context = {
        'total_requests': total_requests,
        'pending': pending,
        'in_progress': in_progress,
        'resolved': resolved,
        'closed': closed,
        'priority_stats': priority_stats,
        'category_stats': category_stats,
        'monthly_stats': monthly_stats,
        'requests': requests[:20],
    }
    
    return render(request, 'maintenance/report.html', context)


@login_required
@require_http_methods(["POST"])
def maintenance_cancel(request, pk):
    """Cancel a maintenance request (tenant only)"""
    request_obj = get_object_or_404(MaintenanceRequest, pk=pk, tenant=request.user)
    
    if request_obj.status not in ['PENDING', 'IN_REVIEW']:
        return JsonResponse({'status': 'error', 'message': 'Request cannot be cancelled.'}, status=400)
    
    request_obj.status = 'CANCELLED'
    request_obj.save()
    
    # Notify owner
    Notification.objects.create(
        user=request_obj.property.owner.user,
        notification_type='MAINTENANCE',
        title='Maintenance Request Cancelled',
        message=f'{request.user.get_full_name()} has cancelled: {request_obj.title}',
        related_object_type='maintenance',
        related_object_id=str(request_obj.id)
    )
    
    return JsonResponse({'status': 'success'})


@login_required
@owner_required
def add_task(request, pk):
    """Add a task to a maintenance request"""
    request_obj = get_object_or_404(MaintenanceRequest, pk=pk)
    
    if request_obj.property.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to add tasks.')
        return redirect('maintenance:list')
    
    if request.method == 'POST':
        form = MaintenanceTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.request = request_obj
            task.save()
            messages.success(request, 'Task added successfully!')
            return redirect('maintenance:detail', pk=request_obj.pk)
    else:
        form = MaintenanceTaskForm()
    
    return render(request, 'maintenance/add_task.html', {
        'form': form,
        'request_obj': request_obj,
    })