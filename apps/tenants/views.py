from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Sum
from django.db import models
from django.urls import reverse 

from .models import TenantApplication, Lease, LeaseAgreementTemplate
from .forms import TenantApplicationForm, LeaseForm
from ..accounts.decorators import tenant_required, owner_required
from ..properties.models import Property, Unit
from ..notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def application_list(request):
    """List tenant's applications"""
    applications = TenantApplication.objects.filter(
        tenant=request.user
    ).select_related('property', 'property__owner')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        applications = applications.filter(status=status_filter)
    
    paginator = Paginator(applications, 10)
    page = request.GET.get('page')
    try:
        applications_page = paginator.page(page)
    except PageNotAnInteger:
        applications_page = paginator.page(1)
    except EmptyPage:
        applications_page = paginator.page(paginator.num_pages)
    
    return render(request, 'tenants/applications.html', {
        'applications': applications_page,
        'status_filter': status_filter,
    })


@login_required
def apply_for_property(request, property_id):
    """Apply for a property as a tenant"""
    property_obj = get_object_or_404(Property, pk=property_id)
    
    # Check if property is available (or has available units)
    if property_obj.is_multi_unit:
        available_units = property_obj.units.filter(is_available=True)
        if not available_units.exists():
            messages.error(request, 'No units are currently available in this building.')
            return redirect('properties:detail', pk=property_id)
    else:
        if property_obj.availability_status != 'AVAILABLE':
            messages.error(request, 'This property is no longer available.')
            return redirect('properties:detail', pk=property_id)
    
    # Check if user already applied for this property
    existing_application = TenantApplication.objects.filter(
        tenant=request.user,
        property=property_obj,
        status__in=['PENDING', 'UNDER_REVIEW']
    ).exists()
    
    if existing_application:
        messages.warning(request, 'You have already applied for this property.')
        return redirect('properties:detail', pk=property_id)
    
    if request.method == 'POST':
        print("POST data:", request.POST)  # Debug: See what's being submitted
        
        form = TenantApplicationForm(request.POST, request.FILES, property_obj=property_obj)
        if form.is_valid():
            application = form.save(commit=False)
            application.tenant = request.user
            application.property = property_obj
            
            # Get the selected unit - IMPORTANT
            unit = form.cleaned_data.get('unit')
            print(f"Selected unit from form: {unit}")  # Debug
            
            if unit:
                application.unit = unit
                print(f"Unit assigned to application: {application.unit.unit_number}")  # Debug
            elif not property_obj.is_multi_unit:
                # For single unit properties, no unit selection needed
                pass
            else:
                # For multi-unit, if no unit selected, show error
                messages.error(request, 'Please select a unit.')
                return render(request, 'tenants/apply.html', {
                    'form': form,
                    'property': property_obj,
                })
            
            application.save()
            
            # Handle documents
            documents = request.FILES.getlist('documents')
            if documents:
                doc_list = []
                for doc in documents:
                    doc_list.append({
                        'name': doc.name,
                        'url': doc.url if hasattr(doc, 'url') else None
                    })
                application.application_documents = doc_list
                application.save()
            
            # Send notification to owner
            unit_info = f" (Unit {unit.unit_number})" if unit else ""
            Notification.objects.create(
                user=property_obj.owner.user,
                notification_type='APPLICATION',
                title='New Tenant Application',
                message=f'{request.user.get_full_name()} has applied for {property_obj.title}{unit_info}',
                related_object_type='application',
                related_object_id=str(application.id),
                data={
                    'property_id': str(property_obj.id),
                    'tenant_id': str(request.user.id),
                    'unit_id': str(unit.id) if unit else None
                }
            )
            
            messages.success(request, f'Application submitted successfully for Unit {unit.unit_number if unit else ""}!')
            return redirect('tenants:application_detail', pk=application.pk)
        else:
            print("Form errors:", form.errors)  # Debug
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TenantApplicationForm(property_obj=property_obj)
    
    return render(request, 'tenants/apply.html', {
        'form': form,
        'property': property_obj,
    })

    
@login_required
def application_detail(request, pk):
    """View application details"""
    application = get_object_or_404(TenantApplication, pk=pk)
    
    # Check permission
    if application.tenant != request.user:
        # Check if user is the owner of the property
        if hasattr(request.user, 'owner_profile'):
            if application.property.owner != request.user.owner_profile:
                messages.error(request, 'You do not have permission to view this application.')
                return redirect('dashboard')
        else:
            messages.error(request, 'You do not have permission to view this application.')
            return redirect('dashboard')
    
    return render(request, 'tenants/application_detail.html', {
        'application': application,
    })


@login_required
@owner_required
def application_review(request, pk):
    """Review tenant application (Owner view)"""
    application = get_object_or_404(TenantApplication, pk=pk)
    
    # Check if owner owns the property
    if application.property.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to review this application.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if status in ['APPROVED', 'REJECTED']:
            application.status = status
            application.owner_notes = notes
            application.reviewed_at = timezone.now()
            application.reviewed_by = request.user
            application.save()
            
            # Create lease if approved
            if status == 'APPROVED':
                # Check if lease already exists
                existing_lease = Lease.objects.filter(
                    tenant=application.tenant,
                    property=application.property,
                    status='ACTIVE'
                ).first()
                
                if not existing_lease:
                    # Calculate end date (default 1 year)
                    end_date = application.intended_move_in_date + timedelta(days=365)
                    
                    Lease.objects.create(
                        tenant=application.tenant,
                        property=application.property,
                        start_date=application.intended_move_in_date,
                        end_date=end_date,
                        monthly_rent=application.property.rental_price,
                        security_deposit=application.property.security_deposit,
                        status='PENDING_SIGNATURE'
                    )
                    
                    # Update property availability
                    application.property.refresh_availability_status()
            
            # Notify tenant
            Notification.objects.create(
                user=application.tenant,
                notification_type='APPLICATION',
                title=f'Application {status.lower()}',
                message=f'Your application for {application.property.title} has been {status.lower()}.',
                related_object_type='application',
                related_object_id=str(application.id)
            )
            
            messages.success(request, f'Application {status.lower()} successfully!')
            return redirect('tenants:application_detail', pk=application.pk)
        else:
            messages.error(request, 'Invalid status selected.')
    
    return render(request, 'tenants/application_review.html', {
        'application': application,
    })


@login_required
@require_http_methods(["POST"])
def cancel_application(request, pk):
    """Cancel a tenant application"""
    application = get_object_or_404(TenantApplication, pk=pk, tenant=request.user)
    
    if application.status not in ['PENDING', 'UNDER_REVIEW']:
        return JsonResponse({'status': 'error', 'message': 'Application cannot be cancelled.'}, status=400)
    
    application.status = 'CANCELLED'
    application.save()
    
    # Notify owner
    Notification.objects.create(
        user=application.property.owner.user,
        notification_type='APPLICATION',
        title='Application Cancelled',
        message=f'{request.user.get_full_name()} has cancelled their application for {application.property.title}',
        related_object_type='application',
        related_object_id=str(application.id)
    )
    
    return JsonResponse({'status': 'success'})


@login_required
def lease_list(request):
    """List user's leases"""
    if request.user.user_type == 'HOUSE_OWNER':
        # Owner sees leases for their properties
        leases = Lease.objects.filter(
            property__owner=request.user.owner_profile
        ).select_related('tenant', 'property', 'unit')
    else:
        # Tenant sees their own leases
        leases = Lease.objects.filter(tenant=request.user).select_related('property', 'unit')
    
    # Filter by status in the view instead of template
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        leases = leases.filter(status=status_filter)
    
    # Count by status for stats
    status_stats = {
        'total': leases.count(),
        'active': leases.filter(status='ACTIVE').count(),
        'pending_signature': leases.filter(status='PENDING_SIGNATURE').count(),
        'expired': leases.filter(status='EXPIRED').count(),
        'terminated': leases.filter(status='TERMINATED').count(),
        'draft': leases.filter(status='DRAFT').count(),
    }
    
    paginator = Paginator(leases, 10)
    page = request.GET.get('page')
    try:
        leases_page = paginator.page(page)
    except PageNotAnInteger:
        leases_page = paginator.page(1)
    except EmptyPage:
        leases_page = paginator.page(paginator.num_pages)
    
    return render(request, 'tenants/lease_list.html', {
        'leases': leases_page,
        'status_filter': status_filter,
        'status_stats': status_stats,
        'status_choices': Lease.LEASE_STATUS,
    })

@login_required
def lease_detail(request, pk):
    """View lease details"""
    lease = get_object_or_404(Lease, pk=pk)
    
    # Check permission
    if lease.tenant != request.user:
        if hasattr(request.user, 'owner_profile'):
            if lease.property.owner != request.user.owner_profile:
                messages.error(request, 'You do not have permission to view this lease.')
                return redirect('dashboard')
        else:
            messages.error(request, 'You do not have permission to view this lease.')
            return redirect('dashboard')
    
    return render(request, 'tenants/lease_detail.html', {
        'lease': lease,
    })


@login_required
@owner_required
def lease_create(request, application_id):
    """Create a lease from an approved application"""
    application = get_object_or_404(TenantApplication, pk=application_id)
    
    # Check if owner owns the property
    if application.property.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to create a lease for this property.')
        return redirect('dashboard')
    
    # Check if application is approved
    if application.status != 'APPROVED':
        messages.error(request, 'Application must be approved before creating a lease.')
        return redirect('tenants:application_detail', pk=application_id)
    
    # Check if lease already exists
    existing_lease = Lease.objects.filter(
        tenant=application.tenant,
        property=application.property,
        unit=application.unit,
        status__in=['ACTIVE', 'PENDING_SIGNATURE']
    ).first()
    
    if existing_lease:
        messages.warning(request, 'A lease already exists for this tenant and unit.')
        return redirect('tenants:lease_detail', pk=existing_lease.pk)
    
    if request.method == 'POST':
        form = LeaseForm(request.POST, request.FILES)
        if form.is_valid():
            lease = form.save(commit=False)
            lease.tenant = application.tenant
            lease.property = application.property
            lease.unit = application.unit
            
            # Use unit pricing if available, otherwise fallback to property pricing
            if application.unit:
                lease.monthly_rent = application.unit.get_rental_price()
                lease.security_deposit = application.unit.get_security_deposit()
            else:
                lease.monthly_rent = application.property.rental_price
                lease.security_deposit = application.property.security_deposit
            
            lease.save()
            
            # Update application status
            application.status = 'APPROVED'
            application.save()
            
            # Update property/unit availability
            if application.unit:
                # Mark unit as booked/rented
                application.unit.status = 'BOOKED'
                application.unit.is_available = False
                application.unit.current_tenant = application.tenant
                application.unit.save()
            else:
                application.property.availability_status = 'RENTED'
                application.property.save()
            
            # Notify tenant
            unit_info = f" (Unit {application.unit.unit_number})" if application.unit else ""
            Notification.objects.create(
                user=application.tenant,
                notification_type='LEASE',
                title='Lease Agreement Created',
                message=f'A lease agreement has been created for {application.property.title}{unit_info}. Please review and sign.',
                related_object_type='lease',
                related_object_id=str(lease.id)
            )
            
            messages.success(request, 'Lease created successfully!')
            return redirect('tenants:lease_detail', pk=lease.pk)
    else:
        # Pre-fill with unit pricing if available
        if application.unit:
            monthly_rent = application.unit.get_rental_price()
            security_deposit = application.unit.get_security_deposit()
        else:
            monthly_rent = application.property.rental_price
            security_deposit = application.property.security_deposit
        
        initial_data = {
            'start_date': application.intended_move_in_date,
            'end_date': application.intended_move_in_date + timedelta(days=365),
            'monthly_rent': monthly_rent,
            'security_deposit': security_deposit,
        }
        form = LeaseForm(initial=initial_data)
    
    return render(request, 'tenants/lease_create.html', {
        'form': form,
        'application': application,
    })

@login_required
def lease_sign(request, pk):
    """Sign a lease agreement (Tenant view)"""
    lease = get_object_or_404(Lease, pk=pk, tenant=request.user)
    
    # Check if user is the tenant on the lease
    if lease.tenant != request.user:
        messages.error(request, 'You are not authorized to sign this lease.')
        return redirect('dashboard')
    
    if lease.status != 'PENDING_SIGNATURE':
        messages.error(request, 'This lease cannot be signed.')
        return redirect('tenants:lease_detail', pk=pk)
    
    if request.method == 'POST':
        # Get the signed lease file
        signed_file = request.FILES.get('signed_lease')
        
        # Mark as signed
        lease.status = 'ACTIVE'
        lease.signed_at = timezone.now()
        
        # Handle signed lease file upload
        if signed_file:
            lease.signed_lease = signed_file
        
        lease.save()
        
        # Update property/unit status
        if lease.unit:
            lease.unit.status = 'RENTED'
            lease.unit.is_available = False
            lease.unit.current_tenant = request.user
            lease.unit.save()
        else:
            lease.property.availability_status = 'RENTED'
            lease.property.save()
        
        # Notify owner
        unit_info = f" (Unit {lease.unit.unit_number})" if lease.unit else ""
        Notification.objects.create(
            user=lease.property.owner.user,
            notification_type='LEASE',
            title='Lease Agreement Signed',
            message=f'{request.user.get_full_name()} has signed the lease agreement for {lease.property.title}{unit_info}',
            related_object_type='lease',
            related_object_id=str(lease.id)
        )
        
        # Create welcome notification for tenant
        Notification.objects.create(
            user=request.user,
            notification_type='LEASE',
            title='Welcome to Your New Home! 🎉',
            message=f'Congratulations! Your lease for {lease.property.title}{unit_info} is now active. Welcome home!',
            related_object_type='lease',
            related_object_id=str(lease.id)
        )
        
        messages.success(request, 'Lease agreement signed successfully! Welcome to your new home! 🎉')
        return redirect('tenants:lease_detail', pk=pk)
    
    return render(request, 'tenants/lease_sign.html', {
        'lease': lease,
    })

@login_required
@owner_required
def lease_terminate(request, pk):
    """Terminate a lease (Owner view)"""
    lease = get_object_or_404(Lease, pk=pk)
    
    # Check if owner owns the property
    if lease.property.owner != request.user.owner_profile:
        messages.error(request, 'You do not have permission to terminate this lease.')
        return redirect('dashboard')
    
    if lease.status != 'ACTIVE':
        messages.error(request, 'Only active leases can be terminated.')
        return redirect('tenants:lease_detail', pk=pk)
    
    if request.method == 'POST':
        termination_reason = request.POST.get('reason', '')
        lease.status = 'TERMINATED'
        lease.terminated_at = timezone.now()
        lease.save()
        
        # Update property availability
        lease.property.refresh_availability_status()
        
        # Notify tenant
        Notification.objects.create(
            user=lease.tenant,
            notification_type='LEASE',
            title='Lease Terminated',
            message=f'Your lease for {lease.property.title} has been terminated. Reason: {termination_reason}',
            related_object_type='lease',
            related_object_id=str(lease.id)
        )
        
        messages.success(request, 'Lease terminated successfully.')
        return redirect('tenants:lease_detail', pk=pk)
    
    return render(request, 'tenants/lease_terminate.html', {
        'lease': lease,
    })

@login_required
@owner_required
def tenant_list(request):
    """List all tenants for owner's properties"""
    from django.db import models
    owner = request.user.owner_profile
    
    # Get all tenants (users with approved applications or active leases)
    approved_applications = TenantApplication.objects.filter(
        property__owner=owner,
        status='APPROVED'
    ).select_related('tenant', 'property')
    
    active_leases = Lease.objects.filter(
        property__owner=owner,
        status='ACTIVE'
    ).select_related('tenant', 'property')
    
    # Combine unique tenants
    tenant_ids = set()
    tenants = []
    
    for app in approved_applications:
        if app.tenant.id not in tenant_ids:
            tenant_ids.add(app.tenant.id)
            tenants.append({
                'user': app.tenant,
                'property': app.property,
                'status': 'Application Approved',
                'joined': app.created_at,
                'lease': None
            })
    
    for lease in active_leases:
        if lease.tenant.id not in tenant_ids:
            tenant_ids.add(lease.tenant.id)
            tenants.append({
                'user': lease.tenant,
                'property': lease.property,
                'status': 'Active Lease',
                'joined': lease.created_at,
                'lease': lease
            })
        else:
            # Update existing tenant with lease info
            for tenant in tenants:
                if tenant['user'].id == lease.tenant.id:
                    tenant['status'] = 'Active Lease'
                    tenant['lease'] = lease
                    break
    
    # Apply filters (on the list, not on queryset)
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'active':
            tenants = [t for t in tenants if t['status'] == 'Active Lease']
        elif status_filter == 'pending':
            tenants = [t for t in tenants if t['status'] == 'Application Approved']
    
    # Search
    search = request.GET.get('search')
    if search:
        search_lower = search.lower()
        tenants = [t for t in tenants if 
                   search_lower in t['user'].first_name.lower() or 
                   search_lower in t['user'].last_name.lower() or
                   search_lower in t['user'].email.lower() or
                   search_lower in t['property'].title.lower()]
    
    # Pagination
    paginator = Paginator(tenants, 20)
    page = request.GET.get('page')
    try:
        tenants_page = paginator.page(page)
    except PageNotAnInteger:
        tenants_page = paginator.page(1)
    except EmptyPage:
        tenants_page = paginator.page(paginator.num_pages)
    
    return render(request, 'tenants/owner_tenant_list.html', {
        'tenants': tenants_page,
        'status_filter': status_filter,
        'search': search,
    })

@login_required
@owner_required
def tenant_detail(request, tenant_id):
    """View tenant details for owner"""
    from django.db import models
    from apps.payments.models import Payment
    from apps.maintenance.models import MaintenanceRequest
    from apps.tenants.models import TenantApplication, Lease
    
    tenant = get_object_or_404(User, id=tenant_id)
    owner = request.user.owner_profile
    
    # Check if tenant is associated with owner's properties
    applications = TenantApplication.objects.filter(
        tenant=tenant,
        property__owner=owner
    )
    
    if not applications.exists():
        messages.error(request, 'This tenant is not associated with your properties.')
        return redirect('tenants:tenant_list')
    
    # Get tenant's active lease
    lease = Lease.objects.filter(
        tenant=tenant,
        property__owner=owner,
        status='ACTIVE'
    ).first()
    
    # Get payment queryset first (before slicing)
    payment_queryset = Payment.objects.filter(
        payer=tenant,
        property__owner=owner
    )
    
    # Calculate stats from the full queryset
    payment_stats = {
        'total': payment_queryset.filter(status='COMPLETED').aggregate(
            total=models.Sum('amount')
        )['total'] or 0,
        'count': payment_queryset.filter(status='COMPLETED').count(),
        'pending': payment_queryset.filter(status='PENDING').count(),
    }
    
    # Then slice for display
    payments = payment_queryset.order_by('-created_at')[:20]
    
    # Get maintenance requests (slice at the end)
    maintenance = MaintenanceRequest.objects.filter(
        tenant=tenant,
        property__owner=owner
    ).order_by('-created_at')[:10]
    
    # Get lease history (no slicing needed if you want all)
    lease_history = Lease.objects.filter(
        tenant=tenant,
        property__owner=owner
    ).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'applications': applications,
        'lease': lease,  # Pass the lease object
        'payments': payments,
        'maintenance': maintenance,
        'lease_history': lease_history,
        'payment_stats': payment_stats,
        'has_active_lease': lease is not None,
    }
    
    return render(request, 'tenants/owner_tenant_detail.html', context)

@login_required
@owner_required
@require_http_methods(["POST"])
def tenant_manage(request, tenant_id):
    """Manage tenant - update status, send notifications, terminate lease, etc."""
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from django.contrib.auth import get_user_model
    from apps.notifications.models import Notification
    from .models import TenantApplication, Lease
    
    User = get_user_model()
    tenant = get_object_or_404(User, id=tenant_id)
    owner = request.user.owner_profile
    
    # Check if tenant is associated with owner's properties
    applications = TenantApplication.objects.filter(
        tenant=tenant,
        property__owner=owner
    )
    
    if not applications.exists():
        return JsonResponse({'status': 'error', 'message': 'Tenant not found'}, status=404)
    
    action = request.POST.get('action')
    
    if action == 'send_notice':
        notice_type = request.POST.get('notice_type')
        message = request.POST.get('message')
        
        if not notice_type or not message:
            return JsonResponse({'status': 'error', 'message': 'Notice type and message are required'}, status=400)
        
        # Create notification
        Notification.objects.create(
            user=tenant,
            notification_type='SYSTEM',
            title=f'Notice from {owner.company_name}',
            message=message,
            data={'notice_type': notice_type}
        )
        
        # Send email notification
        from django.core.mail import send_mail
        send_mail(
            f'Notice: {notice_type}',
            message,
            'noreply@winda.co.ke',
            [tenant.email],
            fail_silently=True
        )
        
        return JsonResponse({'status': 'success', 'message': 'Notice sent successfully'})
    
    elif action == 'update_lease_status':
        lease_id = request.POST.get('lease_id')
        new_status = request.POST.get('status')
        
        if not lease_id or not new_status:
            return JsonResponse({'status': 'error', 'message': 'Lease ID and status are required'}, status=400)
        
        lease = get_object_or_404(Lease, id=lease_id, property__owner=owner)
        
        # Validate status transition
        valid_statuses = ['ACTIVE', 'EXPIRED', 'TERMINATED', 'PENDING_SIGNATURE']
        if new_status not in valid_statuses:
            return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)
        
        # Handle termination specifically
        if new_status == 'TERMINATED':
            lease.status = 'TERMINATED'
            lease.terminated_at = timezone.now()
            lease.save()
            
            # Update property/unit availability
            if lease.unit:
                lease.unit.status = 'AVAILABLE'
                lease.unit.is_available = True
                lease.unit.current_tenant = None
                lease.unit.save()
            else:
                lease.property.availability_status = 'AVAILABLE'
                lease.property.save()
            
            # Notify tenant
            Notification.objects.create(
                user=tenant,
                notification_type='LEASE',
                title='Lease Terminated',
                message=f'Your lease for {lease.property.title} has been terminated.',
                related_object_type='lease',
                related_object_id=str(lease.id)
            )
            
            return JsonResponse({'status': 'success', 'message': 'Lease terminated successfully'})
        else:
            # Other status updates
            lease.status = new_status
            lease.save()
            
            Notification.objects.create(
                user=tenant,
                notification_type='LEASE',
                title=f'Lease Status Updated',
                message=f'Your lease for {lease.property.title} is now {new_status.lower()}.',
                related_object_type='lease',
                related_object_id=str(lease.id)
            )
            
            return JsonResponse({'status': 'success', 'message': f'Lease status updated to {new_status}'})
    
    elif action == 'terminate_lease':
        # Direct termination action (simplified for the button)
        lease_id = request.POST.get('lease_id')
        
        if not lease_id:
            return JsonResponse({'status': 'error', 'message': 'Lease ID is required'}, status=400)
        
        lease = get_object_or_404(Lease, id=lease_id, property__owner=owner)
        
        if lease.status != 'ACTIVE':
            return JsonResponse({'status': 'error', 'message': 'Only active leases can be terminated'}, status=400)
        
        # Terminate the lease
        lease.status = 'TERMINATED'
        lease.terminated_at = timezone.now()
        lease.save()
        
        # Update property/unit availability
        if lease.unit:
            lease.unit.status = 'AVAILABLE'
            lease.unit.is_available = True
            lease.unit.current_tenant = None
            lease.unit.save()
        else:
            lease.property.availability_status = 'AVAILABLE'
            lease.property.save()
        
        # Notify tenant
        Notification.objects.create(
            user=tenant,
            notification_type='LEASE',
            title='Lease Terminated',
            message=f'Your lease for {lease.property.title} has been terminated.',
            related_object_type='lease',
            related_object_id=str(lease.id)
        )
        
        return JsonResponse({'status': 'success', 'message': 'Lease terminated successfully'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

@login_required
@owner_required
def pending_tenants(request):
    """View pending tenant applications for owner's properties"""
    owner = request.user.owner_profile
    
    # Get all pending applications for owner's properties
    applications = TenantApplication.objects.filter(
        property__owner=owner,
        status='PENDING'
    ).select_related('tenant', 'property').order_by('created_at')
    
    # Filter by property
    property_filter = request.GET.get('property')
    if property_filter:
        applications = applications.filter(property_id=property_filter)
    
    # Count by property for stats
    property_stats = applications.values('property__title', 'property__id').annotate(count=Count('id'))
    
    # Get owner's properties for filter dropdown
    properties = Property.objects.filter(owner=owner)
    
    # Pagination
    paginator = Paginator(applications, 20)
    page = request.GET.get('page')
    try:
        applications_page = paginator.page(page)
    except PageNotAnInteger:
        applications_page = paginator.page(1)
    except EmptyPage:
        applications_page = paginator.page(paginator.num_pages)
    
    context = {
        'applications': applications_page,
        'properties': properties,
        'property_filter': property_filter,
        'property_stats': property_stats,
        'total_pending': applications.count(),
    }
    
    return render(request, 'tenants/pending_tenants.html', context)


@login_required
@owner_required
def pending_application_detail(request, pk):
    """View and review a pending application"""
    application = get_object_or_404(TenantApplication, pk=pk)
    owner = request.user.owner_profile
    
    # Check if the application belongs to owner's property
    if application.property.owner != owner:
        messages.error(request, 'You do not have permission to view this application.')
        return redirect('tenants:pending_tenants')
    
    # Check if application is still pending
    if application.status != 'PENDING':
        messages.warning(request, f'This application is already {application.get_status_display()}.')
        return redirect('tenants:application_detail', pk=pk)
    
    # Get other applications for the same property
    similar_applications = TenantApplication.objects.filter(
        property=application.property,
        status='PENDING'
    ).exclude(id=application.id).order_by('created_at')[:5]
    
    # Get tenant's complete profile
    tenant_profile = application.tenant.tenant_profile if hasattr(application.tenant, 'tenant_profile') else None
    
    context = {
        'application': application,
        'tenant_profile': tenant_profile,
        'similar_applications': similar_applications,
        'property': application.property,
    }
    
    return render(request, 'tenants/pending_application_detail.html', context)


@login_required
@owner_required
@require_http_methods(["POST"])
def review_application(request, pk):
    """Review and approve/reject a pending application"""
    application = get_object_or_404(TenantApplication, pk=pk)
    owner = request.user.owner_profile
    
    # Check permission
    if application.property.owner != owner:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    # Check if application is still pending
    if application.status != 'PENDING':
        return JsonResponse({'status': 'error', 'message': 'Application has already been reviewed'}, status=400)
    
    action = request.POST.get('action')  # 'approve' or 'reject'
    notes = request.POST.get('notes', '')
    
    if action == 'approve':
        application.status = 'APPROVED'
        application.owner_notes = notes
        application.reviewed_at = timezone.now()
        application.reviewed_by = request.user
        application.save()
        
        # Check if property is multi-unit
        property_obj = application.property
        
        if property_obj.is_multi_unit:
            # For multi-unit, find an available unit and assign it
            available_unit = property_obj.units.filter(is_available=True).first()
            
            if available_unit:
                # Assign the tenant to this unit
                available_unit.current_tenant = application.tenant
                available_unit.is_available = False
                available_unit.status = 'BOOKED'
                available_unit.save()
                
                # Create lease for this specific unit
                end_date = application.intended_move_in_date + timedelta(days=365)
                lease = Lease.objects.create(
                    tenant=application.tenant,
                    property=application.property,
                    unit=available_unit,  # You'll need to add a unit field to Lease model
                    start_date=application.intended_move_in_date,
                    end_date=end_date,
                    monthly_rent=available_unit.get_rental_price(),
                    security_deposit=available_unit.get_security_deposit(),
                    status='PENDING_SIGNATURE'
                )
                
                # Update property availability
                property_obj.refresh_availability_status()
                
                # Notify tenant
                Notification.objects.create(
                    user=application.tenant,
                    notification_type='APPLICATION',
                    title='Application Approved! 🎉',
                    message=f'Congratulations! Your application for {property_obj.title} - Unit {available_unit.unit_number} has been approved. Please review and sign the lease agreement.',
                    related_object_type='application',
                    related_object_id=str(application.id)
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Application approved! Assigned to Unit {available_unit.unit_number}.',
                    'redirect_url': reverse('tenants:lease_detail', kwargs={'pk': lease.pk})
                })
            else:
                # No available units
                application.status = 'REJECTED'
                application.owner_notes = 'No available units at this time.'
                application.save()
                
                return JsonResponse({
                    'status': 'error',
                    'message': 'No available units for this property.'
                }, status=400)
        else:
            # Single unit property - existing logic
            end_date = application.intended_move_in_date + timedelta(days=365)
            lease = Lease.objects.create(
                tenant=application.tenant,
                property=application.property,
                start_date=application.intended_move_in_date,
                end_date=end_date,
                monthly_rent=application.property.rental_price,
                security_deposit=application.property.security_deposit,
                status='PENDING_SIGNATURE'
            )
            
            # Update property status
            property_obj.availability_status = 'BOOKED'
            property_obj.save()
            
            # Notify tenant
            Notification.objects.create(
                user=application.tenant,
                notification_type='APPLICATION',
                title='Application Approved! 🎉',
                message=f'Congratulations! Your application for {property_obj.title} has been approved. Please review and sign the lease agreement.',
                related_object_type='application',
                related_object_id=str(application.id)
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Application approved successfully!',
                'redirect_url': reverse('tenants:lease_detail', kwargs={'pk': lease.pk})
            })
    
    elif action == 'reject':
        application.status = 'REJECTED'
        application.owner_notes = notes
        application.reviewed_at = timezone.now()
        application.reviewed_by = request.user
        application.save()
        
        # Notify tenant
        Notification.objects.create(
            user=application.tenant,
            notification_type='APPLICATION',
            title='Application Update',
            message=f'Your application for {application.property.title} has been reviewed. Please check the status.',
            related_object_type='application',
            related_object_id=str(application.id)
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Application rejected.',
            'redirect_url': reverse('tenants:pending_tenants')
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

@login_required
@owner_required
def bulk_review_applications(request):
    """Bulk approve/reject applications"""
    owner = request.user.owner_profile
    action = request.POST.get('action')
    application_ids = request.POST.getlist('application_ids[]')
    
    if not application_ids:
        return JsonResponse({'status': 'error', 'message': 'No applications selected'}, status=400)
    
    if action not in ['approve', 'reject']:
        return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
    
    notes = request.POST.get('notes', '')
    approved_count = 0
    rejected_count = 0
    
    for app_id in application_ids:
        try:
            application = TenantApplication.objects.get(id=app_id, property__owner=owner, status='PENDING')
            
            if action == 'approve':
                application.status = 'APPROVED'
                application.owner_notes = notes
                application.reviewed_at = timezone.now()
                application.reviewed_by = request.user
                application.save()
                
                # Create lease
                end_date = application.intended_move_in_date + timedelta(days=365)
                Lease.objects.create(
                    tenant=application.tenant,
                    property=application.property,
                    start_date=application.intended_move_in_date,
                    end_date=end_date,
                    monthly_rent=application.property.rental_price,
                    security_deposit=application.property.security_deposit,
                    status='PENDING_SIGNATURE'
                )
                application.property.refresh_availability_status()
                approved_count += 1
                
            elif action == 'reject':
                application.status = 'REJECTED'
                application.owner_notes = notes
                application.reviewed_at = timezone.now()
                application.reviewed_by = request.user
                application.save()
                rejected_count += 1
                
        except TenantApplication.DoesNotExist:
            continue
    
    return JsonResponse({
        'status': 'success',
        'message': f'Processed {approved_count + rejected_count} applications. Approved: {approved_count}, Rejected: {rejected_count}'
    })

@login_required
@owner_required
@require_http_methods(["POST"])
def bulk_tenant_action(request):
    """Bulk action for tenants"""
    owner = request.user.owner_profile
    action = request.POST.get('action')
    tenant_ids = request.POST.getlist('tenant_ids[]')
    
    if not tenant_ids:
        return JsonResponse({'status': 'error', 'message': 'No tenants selected'}, status=400)
    
    if action == 'send_message':
        message = request.POST.get('message')
        subject = request.POST.get('subject', 'Message from Property Owner')
        
        for tenant_id in tenant_ids:
            tenant = get_object_or_404(User, id=tenant_id)
            
            # Create notification
            Notification.objects.create(
                user=tenant,
                notification_type='SYSTEM',
                title=subject,
                message=message,
                data={'from_owner': str(owner.id)}
            )
        
        return JsonResponse({'status': 'success', 'message': f'Message sent to {len(tenant_ids)} tenants'})
    
    elif action == 'export_data':
        # Generate CSV export
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tenants_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Phone', 'Property', 'Status', 'Joined'])
        
        for tenant_id in tenant_ids:
            tenant = get_object_or_404(User, id=tenant_id)
            app = TenantApplication.objects.filter(
                tenant=tenant,
                property__owner=owner
            ).first()
            
            if app:
                writer.writerow([
                    tenant.get_full_name(),
                    tenant.email,
                    tenant.phone,
                    app.property.title,
                    app.get_status_display(),
                    app.created_at.strftime('%Y-%m-%d')
                ])
        
        return response
    
    return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
