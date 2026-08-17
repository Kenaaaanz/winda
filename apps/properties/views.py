from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import os

from .models import Property, PropertyImage, PropertyDocument, Favorite, Unit
from .forms import PropertyForm, PropertySearchForm, PropertyDocumentForm, UnitForm, UnitFormSet
from .services import PropertyService
from ..accounts.decorators import owner_required
from ..tenants.models import TenantApplication
from ..payments.models import Payment
from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler




# ==================== PUBLIC VIEWS ====================

def property_list(request):
    """Public property listing page with search and filters"""
    form = PropertySearchForm(request.GET or None)
    
    # Get ALL verified properties, not just available
    properties = Property.objects.filter(
        verification_status='VERIFIED'
    )
    
    # Apply filters
    if form.is_valid():
        # Location filter
        if form.cleaned_data.get('city'):
            properties = properties.filter(
                Q(city__icontains=form.cleaned_data['city']) |
                Q(state__icontains=form.cleaned_data['city'])
            )
        
        # Price range
        min_price = form.cleaned_data.get('min_price')
        max_price = form.cleaned_data.get('max_price')
        if min_price:
            properties = properties.filter(rental_price__gte=min_price)
        if max_price:
            properties = properties.filter(rental_price__lte=max_price)
        
        # Property type
        if form.cleaned_data.get('property_type'):
            properties = properties.filter(property_type=form.cleaned_data['property_type'])
        
        # Bedrooms
        if form.cleaned_data.get('bedrooms'):
            properties = properties.filter(bedrooms=form.cleaned_data['bedrooms'])
        
        # Amenities
        amenities = form.cleaned_data.get('amenities')
        if amenities:
            for amenity in amenities:
                properties = properties.filter(amenities__contains=[amenity])
        
        # Search text
        search_text = form.cleaned_data.get('search_text')
        if search_text:
            properties = properties.filter(
                Q(title__icontains=search_text) |
                Q(description__icontains=search_text) |
                Q(address__icontains=search_text)
            )
        
        # Availability filter - default to AVAILABLE if not specified
        availability_filter = request.GET.get('availability', 'AVAILABLE')
        if availability_filter == 'all':
            pass  # Show all
        elif availability_filter:
            properties = properties.filter(availability_status=availability_filter)
        else:
            # Default: only show available
            properties = properties.filter(availability_status='AVAILABLE')
        
        # Near me (location based)
        latitude = form.cleaned_data.get('latitude')
        longitude = form.cleaned_data.get('longitude')
        radius = form.cleaned_data.get('radius')
        
        if latitude and longitude and radius:
            # Simple distance calculation without PostGIS
            # You can implement distance calculation here
            pass
    
    # Sort
    sort_by = request.GET.get('sort', 'created_at')
    if sort_by == 'price_low':
        properties = properties.order_by('rental_price')
    elif sort_by == 'price_high':
        properties = properties.order_by('-rental_price')
    elif sort_by == 'popular':
        properties = properties.order_by('-view_count')
    else:
        properties = properties.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(properties, 12)
    page = request.GET.get('page')
    try:
        properties_page = paginator.page(page)
    except PageNotAnInteger:
        properties_page = paginator.page(1)
    except EmptyPage:
        properties_page = paginator.page(paginator.num_pages)
    
    context = {
        'properties': properties_page,
        'form': form,
        'property_types': Property.PROPERTY_TYPES,
        'amenities_list': PropertyService.get_amenities_list(),
        'availability_choices': Property.AVAILABILITY_STATUS,
    }
    return render(request, 'properties/list.html', context)

@login_required
def property_detail(request, pk):
    """Property detail page"""
    property_obj = get_object_or_404(Property, pk=pk)
    
    # Check if property is verified or user is owner
    if property_obj.verification_status != 'VERIFIED':
        if not request.user.is_authenticated or property_obj.owner.user != request.user:
            messages.warning(request, 'This property is not yet verified.')
    
    # Increment view count
    property_obj.increment_view_count()
    
    # Get similar properties
    similar_properties = PropertyService.get_similar_properties(property_obj)
    
    # Check if user has this property in favorites
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(
            user=request.user,
            property=property_obj
        ).exists()
    
    # Get unit information
    unit_count = property_obj.units.count() if property_obj.is_multi_unit else 1
    available_units = property_obj.get_available_units_count()
    units = property_obj.units.all() if property_obj.is_multi_unit else []
    
    context = {
        'property': property_obj,
        'similar_properties': similar_properties,
        'is_favorited': is_favorited,
        'amenities_list': PropertyService.get_amenities_list(),
        'property_features': PropertyService.get_features_list(),
        'is_owner': request.user.is_authenticated and property_obj.owner.user == request.user,
        'unit_count': unit_count,
        'available_units': available_units,
        'units': units,
    }
    return render(request, 'properties/detail.html', context)

def property_search_autocomplete(request):
    """AJAX endpoint for property search autocomplete"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    properties = Property.objects.filter(
        Q(title__icontains=query) |
        Q(city__icontains=query) |
        Q(address__icontains=query),
        verification_status='VERIFIED',
        availability_status='AVAILABLE'
    ).values('id', 'title', 'city', 'address')[:10]
    
    suggestions = []
    for prop in properties:
        suggestions.append({
            'id': prop['id'],
            'label': f"{prop['title']} - {prop['city']}",
            'value': prop['address']
        })
    
    return JsonResponse({'suggestions': suggestions})


# ==================== OWNER VIEWS ====================

@login_required
@owner_required
def property_create(request):
    """Create new property listing with optional units"""
    from .forms import PropertyWithUnitsForm
    from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler
    import time
    
    if request.method == 'POST':
        form = PropertyWithUnitsForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                property_obj = form.save(commit=False)
                property_obj.owner = request.user.owner_profile
                
                # Handle amenities and features
                amenities = request.POST.getlist('amenities')
                features = request.POST.getlist('features')
                property_obj.amenities = amenities if amenities else []
                property_obj.features = features if features else []
                
                # Handle main image
                main_image = request.FILES.get('main_image')
                if main_image:
                    try:
                        compressed = CloudinaryImageHandler.compress_image(main_image)
                        unique_id = f"main_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                        result = CloudinaryService.upload_property_image(
                            compressed, 
                            str(property_obj.id) if property_obj.id else f'temp_{int(time.time())}',
                            f'main_{unique_id}'
                        )
                        if result:
                            property_obj.main_image = result['secure_url']
                            public_id = result.get('public_id', '')
                            if len(public_id) > 500:
                                public_id = public_id[:500]
                            property_obj.main_image_public_id = public_id
                    except Exception as e:
                        print(f"Main image upload error: {e}")
                
                # Handle multi-unit
                is_multi_unit = form.cleaned_data.get('is_multi_unit', False)
                property_obj.is_multi_unit = is_multi_unit
                
                if not is_multi_unit:
                    property_obj.total_units = 1
                    property_obj.available_units = 1
                else:
                    property_obj.total_units = form.cleaned_data.get('total_units', 1)
                    property_obj.available_units = form.cleaned_data.get('total_units', 1)
                
                property_obj.save()
                
                # Handle gallery images
                images = request.FILES.getlist('images')
                for idx, image in enumerate(images):
                    try:
                        compressed = CloudinaryImageHandler.compress_image(image)
                        unique_id = f"gal_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                        result = CloudinaryService.upload_property_image(
                            compressed,
                            str(property_obj.id),
                            f'gallery_{unique_id}'
                        )
                        if result:
                            public_id = result.get('public_id', '')
                            if len(public_id) > 500:
                                public_id = public_id[:500]
                            PropertyImage.objects.create(
                                property=property_obj,
                                image=result['secure_url'],
                                cloudinary_public_id=public_id,
                                is_main=(idx == 0 and not property_obj.main_image),
                                order=idx
                            )
                    except Exception as e:
                        print(f"Gallery image {idx} upload error: {e}")
                        continue
                
                # Handle units for multi-unit properties
                if is_multi_unit:
                    messages.success(request, 'Property created! Now add your units.')
                    return redirect('properties:manage_units', pk=property_obj.pk)
                else:
                    messages.success(request, 'Property created successfully!')
                    return redirect('properties:detail', pk=property_obj.pk)
                    
            except Exception as e:
                messages.error(request, f'Error creating property: {str(e)}')
                return redirect('properties:create')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    # GET request or invalid POST - display the form
    form = PropertyWithUnitsForm()
    amenities_list = PropertyService.get_amenities_list()
    features_list = PropertyService.get_features_list()
    
    return render(request, 'properties/create.html', {
        'form': form,
        'amenities': amenities_list,
        'features': features_list,
    })

@login_required
@owner_required
def manage_units(request, pk):
    """Manage units for a multi-unit property"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if not property_obj.is_multi_unit:
        messages.warning(request, 'This property is not set as multi-unit.')
        return redirect('properties:edit', pk=property_obj.pk)
    
    if request.method == 'POST':
        formset = UnitFormSet(request.POST, queryset=property_obj.units.all())
        
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.property_obj = property_obj
                # Ensure amenities and features are lists
                if not instance.amenities:
                    instance.amenities = []
                if not instance.features:
                    instance.features = []
                instance.save()
            
            # Delete marked instances
            for obj in formset.deleted_objects:
                obj.delete()
            
            # Update available units count
            available_count = property_obj.units.filter(is_available=True).count()
            property_obj.available_units = available_count
            property_obj.total_units = property_obj.units.count()
            property_obj.save()
            
            messages.success(request, 'Units updated successfully!')
            return redirect('properties:manage_units', pk=property_obj.pk)
        else:
            # Print formset errors for debugging
            for form in formset:
                if form.errors:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'Unit {form.instance.unit_number if form.instance.unit_number else "new"}: {field} - {error}')
    else:
        formset = UnitFormSet(queryset=property_obj.units.all())
    
    amenities = PropertyService.get_amenities_list()
    features = PropertyService.get_features_list()
    
    return render(request, 'properties/manage_units.html', {
        'property': property_obj,
        'formset': formset,
        'amenities': amenities,
        'features': features,
        'unit_count': property_obj.units.count(),
    })

@login_required
@owner_required
def bulk_add_units(request, pk):
    """Bulk add units to a property with pricing"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        unit_count = int(request.POST.get('unit_count', 0))
        start_unit = request.POST.get('start_unit_number', '1')
        default_bedrooms = int(request.POST.get('default_bedrooms', 1))
        default_bathrooms = int(request.POST.get('default_bathrooms', 1))
        
        # Get pricing from form or use property defaults
        default_rent = request.POST.get('default_rental_price', '')
        default_service = request.POST.get('default_service_charge', '')
        default_deposit = request.POST.get('default_security_deposit', '')
        
        # Use property defaults if not specified
        if not default_rent:
            default_rent = property_obj.rental_price
        if not default_service:
            default_service = property_obj.service_charge
        if not default_deposit:
            default_deposit = property_obj.security_deposit
        
        if unit_count <= 0:
            messages.error(request, 'Please enter a valid number of units.')
            return redirect('properties:manage_units', pk=property_obj.pk)
        
        created_count = 0
        errors = []
        
        # Determine if start_unit is numeric or alphanumeric
        if start_unit.isdigit():
            start_num = int(start_unit)
            for i in range(unit_count):
                unit_number = str(start_num + i)
                if not property_obj.units.filter(unit_number=unit_number).exists():
                    try:
                        Unit.objects.create(
                            property_obj=property_obj,
                            unit_number=unit_number,
                            bedrooms=default_bedrooms,
                            bathrooms=default_bathrooms,
                            rental_price=default_rent,
                            service_charge=default_service,
                            security_deposit=default_deposit,
                            amenities=[],
                            features=[],
                            is_available=True,
                            status='AVAILABLE'
                        )
                        created_count += 1
                    except Exception as e:
                        errors.append(f'Unit {unit_number}: {str(e)}')
                else:
                    errors.append(f'Unit {unit_number} already exists')
        else:
            # Alphanumeric (e.g., A1, A2)
            prefix = ''.join([c for c in start_unit if not c.isdigit()])
            start_num = int(''.join([c for c in start_unit if c.isdigit()]) or 1)
            for i in range(unit_count):
                unit_number = f"{prefix}{start_num + i}"
                if not property_obj.units.filter(unit_number=unit_number).exists():
                    try:
                        Unit.objects.create(
                            property_obj=property_obj,
                            unit_number=unit_number,
                            bedrooms=default_bedrooms,
                            bathrooms=default_bathrooms,
                            rental_price=default_rent,
                            service_charge=default_service,
                            security_deposit=default_deposit,
                            amenities=[],
                            features=[],
                            is_available=True,
                            status='AVAILABLE'
                        )
                        created_count += 1
                    except Exception as e:
                        errors.append(f'Unit {unit_number}: {str(e)}')
                else:
                    errors.append(f'Unit {unit_number} already exists')
        
        # Update total units
        property_obj.total_units = property_obj.units.count()
        property_obj.available_units = property_obj.units.filter(is_available=True).count()
        property_obj.save()
        
        if errors:
            messages.warning(request, f'{created_count} units added. Errors: {", ".join(errors[:5])}')
        else:
            messages.success(request, f'{created_count} units added successfully!')
        
        return redirect('properties:manage_units', pk=property_obj.pk)
    
    return redirect('properties:manage_units', pk=property_obj.pk)

    
@login_required
@owner_required
@require_http_methods(["POST"])
def toggle_unit_availability(request, unit_id):
    """Toggle unit availability"""
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from .models import Unit
    
    try:
        unit = get_object_or_404(Unit, id=unit_id)
        property_obj = unit.property_obj
        
        # Check if user owns the property
        if property_obj.owner != request.user.owner_profile:
            return JsonResponse({
                'status': 'error', 
                'message': 'You do not have permission to modify this unit.'
            }, status=403)
        
        # Toggle availability
        unit.is_available = not unit.is_available
        unit.status = 'AVAILABLE' if unit.is_available else 'RENTED'
        unit.save()
        
        # Update property available units count
        available_count = property_obj.units.filter(is_available=True).count()
        property_obj.available_units = available_count
        property_obj.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Unit {unit.unit_number} is now {"available" if unit.is_available else "unavailable"}',
            'is_available': unit.is_available,
            'status_display': unit.get_status_display(),
            'available_count': available_count,
            'unit_number': unit.unit_number
        })
        
    except Unit.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Unit not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    
@login_required
@owner_required
@require_http_methods(["POST"])
def delete_unit(request, unit_id):
    """Delete a unit"""
    unit = get_object_or_404(Unit, id=unit_id)
    property_obj = unit.property_obj
    
    # Check if user owns the property
    if property_obj.owner != request.user.owner_profile:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    # Check if unit has a current tenant
    if unit.current_tenant:
        return JsonResponse({
            'status': 'error', 
            'message': 'Cannot delete a unit with a current tenant. Please remove the tenant first.'
        }, status=400)
    
    unit.delete()
    
    # Update property total units
    property_obj.total_units = property_obj.units.count()
    property_obj.available_units = property_obj.units.filter(is_available=True).count()
    property_obj.save()
    
    return JsonResponse({'status': 'success', 'message': 'Unit deleted successfully'})


@login_required
def unit_detail(request, unit_id):
    """View unit details (public view)"""
    unit = get_object_or_404(Unit, id=unit_id)
    property_obj = unit.property_obj
    
    # Check if property is verified and visible
    if property_obj.verification_status != 'VERIFIED':
        messages.warning(request, 'This property is not yet verified.')
    
    return render(request, 'properties/unit_detail.html', {
        'unit': unit,
        'property': property_obj,
    })


@login_required
@owner_required
def update_units(request, pk):
    """Update units for a property (AJAX endpoint for individual unit updates)"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        unit_id = request.POST.get('unit_id')
        field = request.POST.get('field')
        value = request.POST.get('value')
        
        if not unit_id or not field:
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
        
        unit = get_object_or_404(Unit, id=unit_id, property_obj=property_obj)
        
        # Update the specified field
        if field in ['unit_number', 'floor_number', 'bedrooms', 'bathrooms', 'square_feet']:
            if field == 'floor_number':
                value = int(value) if value else None
            elif field in ['bedrooms', 'bathrooms', 'square_feet']:
                value = int(value) if value else 0
            setattr(unit, field, value)
            unit.save()
            
            return JsonResponse({'status': 'success', 'message': f'{field} updated successfully'})
        
        return JsonResponse({'status': 'error', 'message': 'Invalid field'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
@owner_required
def property_edit(request, pk):
    """Edit property listing"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property_obj)
        if form.is_valid():
            property_obj = form.save(commit=False)
            availability_status = request.POST.get('availability_status')
            if availability_status in dict(Property.AVAILABILITY_STATUS):
                property_obj.availability_status = availability_status
            property_obj.save()
            messages.success(request, 'Property updated successfully!')
            return redirect('properties:detail', pk=property_obj.pk)
    else:
        form = PropertyForm(instance=property_obj)
    
    context = {
        'form': form,
        'property': property_obj,
        'amenities': PropertyService.get_amenities_list(),
        'features': PropertyService.get_features_list(),
    }
    return render(request, 'properties/edit.html', context)


@login_required
@owner_required
def property_delete(request, pk):
    """Delete property listing"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        property_obj.delete()
        messages.success(request, 'Property deleted successfully!')
        return redirect('properties:owner_properties')
    
    return render(request, 'properties/delete.html', {'property': property_obj})

@login_required
@owner_required
def owner_properties(request):
    """List all properties for the owner with full management"""
    owner = request.user.owner_profile
    
    # Get ALL properties, regardless of status
    properties = Property.objects.filter(owner=owner)
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        properties = properties.filter(availability_status=status_filter)
    
    # Verification filter
    verification_filter = request.GET.get('verification', 'all')
    if verification_filter != 'all':
        properties = properties.filter(verification_status=verification_filter)
    
    # Annotate with tenant and pending counts BEFORE pagination
    properties = properties.annotate(
        tenant_count=Count('applications', filter=Q(applications__status='APPROVED'), distinct=True),
        pending_count=Count('applications', filter=Q(applications__status='PENDING'), distinct=True)
    )
    
    # Order by latest
    properties = properties.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(properties, 10)
    page = request.GET.get('page')
    try:
        properties_page = paginator.page(page)
    except PageNotAnInteger:
        properties_page = paginator.page(1)
    except EmptyPage:
        properties_page = paginator.page(paginator.num_pages)
    
    # Stats
    stats = {
        'total': Property.objects.filter(owner=owner).count(),
        'available': Property.objects.filter(owner=owner, availability_status='AVAILABLE').count(),
        'rented': Property.objects.filter(owner=owner, availability_status='RENTED').count(),
        'booked': Property.objects.filter(owner=owner, availability_status='BOOKED').count(),
        'under_maintenance': Property.objects.filter(owner=owner, availability_status='UNDER_MAINTENANCE').count(),
        'total_revenue': Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    context = {
        'properties': properties_page,
        'stats': stats,
        'search_query': search_query,
        'status_filter': status_filter,
        'verification_filter': verification_filter,
        'availability_statuses': Property.AVAILABILITY_STATUS,
        'verification_statuses': Property.VERIFICATION_STATUS,
    }
    
    return render(request, 'properties/owner_properties.html', context)

    
@login_required
@owner_required
def property_dashboard(request, pk):
    """Owner dashboard for a specific property"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    from apps.tenants.models import TenantApplication
    from apps.payments.models import Payment
    from apps.maintenance.models import MaintenanceRequest

    pending_applications = TenantApplication.objects.filter(property=property_obj, status='PENDING')
    applications = TenantApplication.objects.filter(property=property_obj).order_by('-created_at')[:5]
    pending_maintenance_count = MaintenanceRequest.objects.filter(
        property=property_obj,
        status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
    ).count()
    total_revenue = Payment.objects.filter(property=property_obj, status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0

    recent_activity = []
    for app in applications:
        recent_activity.append({
            'description': f'Application from {app.tenant.get_full_name()}',
            'icon': 'file-signature',
            'timestamp': app.created_at,
            'status': app.status,
            'color': 'blue',
        })

    context = {
        'property': property_obj,
        'view_count': property_obj.view_count,
        'favorite_count': property_obj.favorites.count(),
        'inquiry_count': TenantApplication.objects.filter(property=property_obj).count(),
        'total_revenue': total_revenue,
        'pending_applications_count': pending_applications.count(),
        'pending_maintenance_count': pending_maintenance_count,
        'applications': applications,
        'recent_activity': recent_activity,
    }
    return render(request, 'properties/property_dashboard.html', context)


@login_required
@owner_required
def property_tenants(request, pk):
    """Manage tenants and applications for a property"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    from apps.tenants.models import TenantApplication, Lease
    from apps.payments.models import Payment
    from apps.maintenance.models import MaintenanceRequest

    pending_applications = TenantApplication.objects.filter(property=property_obj, status='PENDING').select_related('tenant')
    tenants = Lease.objects.filter(property=property_obj, status='ACTIVE').select_related('tenant')

    for lease in tenants:
        lease.move_in_date = lease.start_date
        lease.total_paid = Payment.objects.filter(lease=lease, status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
        lease.maintenance_requests = MaintenanceRequest.objects.filter(property=property_obj, tenant=lease.tenant)

    context = {
        'property': property_obj,
        'pending_applications': pending_applications,
        'tenants': tenants,
    }
    return render(request, 'properties/property_tenants.html', context)


@login_required
@owner_required
def property_payments(request, pk):
    """View payments for a property"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    from apps.payments.models import Payment

    status_filter = request.GET.get('status', 'all')
    payments = property_obj.payments.all().order_by('-created_at')
    if status_filter != 'all':
        payments = payments.filter(status=status_filter)

    total_rent = property_obj.payments.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
    pending_amount = property_obj.payments.filter(status='PENDING').aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'property': property_obj,
        'payments': payments,
        'total_rent': total_rent,
        'pending_amount': pending_amount,
        'status_filter': status_filter,
    }
    return render(request, 'properties/property_payments.html', context)


@login_required
@owner_required
def property_maintenance(request, pk):
    """View and filter maintenance requests for a property"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    from apps.maintenance.models import MaintenanceRequest

    status_filter = request.GET.get('status', 'all')
    requests = MaintenanceRequest.objects.filter(property=property_obj).order_by('-created_at')
    if status_filter != 'all':
        requests = requests.filter(status=status_filter)

    paginator = Paginator(requests, 12)
    page = request.GET.get('page')
    try:
        requests_page = paginator.page(page)
    except PageNotAnInteger:
        requests_page = paginator.page(1)
    except EmptyPage:
        requests_page = paginator.page(paginator.num_pages)

    context = {
        'property': property_obj,
        'requests': requests_page,
        'status_choices': MaintenanceRequest.STATUS_CHOICES,
        'status_filter': status_filter,
    }
    return render(request, 'properties/property_maintenance.html', context)


# ==================== IMAGE MANAGEMENT VIEWS ====================

@login_required
@owner_required
def property_images_manage(request, pk):
    """Manage property images - set main, thumbnail, reorder, delete"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    images = property_obj.property_images.filter(is_active=True).order_by('order')
    
    context = {
        'property': property_obj,
        'images': images,
    }
    
    return render(request, 'properties/manage_images.html', context)


@login_required
@owner_required
def upload_property_images(request, pk):
    """Upload multiple images for a property using Cloudinary"""
    from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler
    from django.db import models
    import time
    import uuid
    
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    images = request.FILES.getlist('images')
    
    if not images:
        return JsonResponse({'status': 'error', 'message': 'No images provided'}, status=400)
    
    uploaded = []
    errors = []
    
    for idx, img in enumerate(images):
        try:
            # Generate a unique public_id - keep it shorter
            unique_id = f"prop_{str(property_obj.id)[:8]}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            
            # Upload to Cloudinary
            result = CloudinaryService.upload_property_image(
                img,
                str(property_obj.id),
                f'gallery_{unique_id}'
            )
            
            if result:
                # Get the public_id from Cloudinary response (might be long)
                public_id = result.get('public_id', '')
                
                # Truncate if it's too long (just in case)
                if len(public_id) > 500:
                    public_id = public_id[:500]
                
                # Check if this public_id already exists
                existing = property_obj.property_images.filter(
                    cloudinary_public_id=public_id,
                    is_active=True
                ).first()
                
                if existing:
                    # If it exists, generate a new unique one
                    public_id = f"{public_id[:200]}_{uuid.uuid4().hex[:4]}"
                    if len(public_id) > 500:
                        public_id = public_id[:500]
                
                # Get the current max order
                max_order = property_obj.property_images.filter(is_active=True).aggregate(
                    models.Max('order')
                )['order__max'] or 0
                order_value = max_order + idx + 1
                
                property_image = PropertyImage.objects.create(
                    property=property_obj,
                    image=result['secure_url'],
                    cloudinary_public_id=public_id,
                    is_main=(idx == 0 and not property_obj.main_image),
                    order=order_value,
                    is_active=True
                )
                
                # If this is the first image and no main image exists, set as main
                if idx == 0 and not property_obj.main_image:
                    property_obj.main_image = result['secure_url']
                    property_obj.main_image_public_id = public_id
                    property_obj.save(update_fields=['main_image', 'main_image_public_id'])
                
                uploaded.append({
                    'id': str(property_image.id),
                    'url': result['secure_url'],
                    'thumbnail': CloudinaryService.get_thumbnail_url(public_id, 200, 150),
                    'public_id': public_id
                })
        except Exception as e:
            errors.append(f"Image {idx+1}: {str(e)}")
            print(f"Error uploading image {idx}: {str(e)}")
            continue
    
    # If no main image was set, set the first uploaded as main
    if not property_obj.main_image and uploaded:
        first_image = property_obj.property_images.filter(is_active=True).order_by('order').first()
        if first_image:
            first_image.is_main = True
            first_image.save()
            property_obj.main_image = first_image.image
            property_obj.main_image_public_id = first_image.cloudinary_public_id
            property_obj.save(update_fields=['main_image', 'main_image_public_id'])
    
    if uploaded:
        return JsonResponse({
            'status': 'success',
            'message': f'{len(uploaded)} images uploaded successfully',
            'images': uploaded,
            'errors': errors
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'No images were uploaded successfully',
            'errors': errors
        }, status=400)
    
@login_required
@owner_required
@require_http_methods(["POST"])
def set_main_image(request, pk, image_id):
    """Set a property image as the main image"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    try:
        # Try to get by UUID first, then by integer ID
        try:
            image = property_obj.property_images.get(id=image_id, is_active=True)
        except (ValueError, TypeError):
            # If image_id is not a valid UUID, try as integer
            image = property_obj.property_images.get(id=int(image_id), is_active=True)
        
        # Reset all images to not main
        property_obj.property_images.filter(is_active=True).update(is_main=False)
        
        # Set selected image as main
        image.is_main = True
        image.save()
        
        # Also update property's main_image field
        property_obj.main_image = image.image
        property_obj.save(update_fields=['main_image'])
        
        return JsonResponse({'status': 'success', 'message': 'Main image updated successfully'})
    except (PropertyImage.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@owner_required
@require_http_methods(["POST"])
def set_thumbnail(request, pk, image_id):
    """Set a property image as the thumbnail"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    try:
        # Try to get by UUID first, then by integer ID
        try:
            image = property_obj.property_images.get(id=image_id, is_active=True)
        except (ValueError, TypeError):
            image = property_obj.property_images.get(id=int(image_id), is_active=True)
        
        property_obj.thumbnail = image.image
        property_obj.save(update_fields=['thumbnail'])
        
        return JsonResponse({'status': 'success', 'message': 'Thumbnail updated successfully'})
    except (PropertyImage.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@owner_required
@require_http_methods(["POST"])
def update_image_caption(request, pk, image_id):
    """Update image caption"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    caption = request.POST.get('caption', '')
    
    try:
        # Try to get by UUID first, then by integer ID
        try:
            image = property_obj.property_images.get(id=image_id, is_active=True)
        except (ValueError, TypeError):
            image = property_obj.property_images.get(id=int(image_id), is_active=True)
        
        image.caption = caption
        image.save(update_fields=['caption'])
        return JsonResponse({'status': 'success', 'message': 'Caption updated successfully'})
    except (PropertyImage.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
@login_required
@owner_required
@require_http_methods(["POST"])
def reorder_images(request, pk):
    """Reorder property images"""
    import json
    from django.db import models
    
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    order_data = json.loads(request.POST.get('order_data', '[]'))
    
    if not order_data:
        return JsonResponse({'status': 'error', 'message': 'No order data provided'}, status=400)
    
    try:
        # Update orders in a transaction
        for item in order_data:
            image_id = item.get('id')
            new_order = item.get('order')
            
            if image_id and new_order is not None:
                # Use update() to bypass any constraints temporarily
                PropertyImage.objects.filter(
                    id=image_id,
                    property=property_obj,
                    is_active=True
                ).update(order=new_order)
        
        return JsonResponse({'status': 'success', 'message': 'Images reordered successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@owner_required
@require_http_methods(["POST"])
def delete_property_image(request, pk):
    """Delete a property image"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    image_id = request.POST.get('image_id')
    
    if not image_id:
        return JsonResponse({'status': 'error', 'message': 'Image ID required'}, status=400)
    
    try:
        image = property_obj.property_images.get(id=image_id, is_active=True)
        
        # Delete from Cloudinary
        if image.cloudinary_public_id:
            try:
                from apps.common.utils.cloudinary_utils import CloudinaryService
                CloudinaryService.delete_image(image.cloudinary_public_id)
            except:
                pass
        
        # Check if this is the main image
        if image.is_main or (property_obj.main_image and property_obj.main_image == image.image):
            # Set a new main image if available
            other_images = property_obj.property_images.filter(is_active=True).exclude(id=image_id)
            if other_images.exists():
                new_main = other_images.first()
                new_main.is_main = True
                new_main.save()
                property_obj.main_image = new_main.image
                property_obj.save(update_fields=['main_image'])
            else:
                property_obj.main_image = None
                property_obj.save(update_fields=['main_image'])
        
        # Check if this is the thumbnail
        if property_obj.thumbnail and property_obj.thumbnail == image.image:
            # Set new thumbnail if available
            other_images = property_obj.property_images.filter(is_active=True).exclude(id=image_id)
            if other_images.exists():
                property_obj.thumbnail = other_images.first().image
            elif property_obj.main_image:
                property_obj.thumbnail = property_obj.main_image
            else:
                property_obj.thumbnail = None
            property_obj.save(update_fields=['thumbnail'])
        
        # Soft delete
        image.is_active = False
        image.save()
        
        return JsonResponse({'status': 'success', 'message': 'Image deleted successfully'})
    except PropertyImage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    

# ==================== FAVORITE VIEWS ====================

@login_required
def toggle_favorite(request, pk):
    """Toggle property favorite status"""
    property_obj = get_object_or_404(Property, pk=pk)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        property=property_obj
    )
    if not created:
        favorite.delete()
        return JsonResponse({
            'status': 'removed',
            'favorite_count': property_obj.favorites.count()
        })
    return JsonResponse({
        'status': 'added',
        'favorite_count': property_obj.favorites.count()
    })


@login_required
def favorites_list(request):
    """List user's favorite properties"""
    favorites = Favorite.objects.filter(user=request.user).select_related('property')
    paginator = Paginator(favorites, 12)
    page = request.GET.get('page')
    try:
        favorites_page = paginator.page(page)
    except PageNotAnInteger:
        favorites_page = paginator.page(1)
    except EmptyPage:
        favorites_page = paginator.page(paginator.num_pages)
    
    return render(request, 'properties/favorites.html', {
        'favorites': favorites_page,
    })


# ==================== DOCUMENT VIEWS ====================

@login_required
@owner_required
def upload_document(request, pk):
    """Upload property document"""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        form = PropertyDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.property = property_obj
            doc.save()
            messages.success(request, 'Document uploaded successfully!')
            return redirect('properties:detail', pk=property_obj.pk)
    else:
        form = PropertyDocumentForm()
    
    return render(request, 'properties/upload_document.html', {
        'form': form,
        'property': property_obj,
    })


@login_required
@owner_required
@require_http_methods(["POST"])
def delete_document(request, doc_id):
    """Delete property document"""
    doc = get_object_or_404(PropertyDocument, id=doc_id)
    if doc.property.owner != request.user.owner_profile:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    doc.delete()
    return JsonResponse({'status': 'success'})

