from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.urls import reverse
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import models
from django.views.decorators.http import require_http_methods



from .models import User, UserProfile, OwnerProfile, TenantProfile, LoginHistory
from .forms import (
    PaystackSubaccountForm, UserRegistrationForm, UserLoginForm, UserProfileForm,
    OwnerProfileForm, TenantProfileForm, UserUpdateForm,
    CustomPasswordChangeForm, PasswordResetForm
)
from .tokens import account_activation_token
from .decorators import user_type_required, owner_required, tenant_required
from apps.emails.utils import EmailService


from apps.emails.utils import EmailService

def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Deactivate until email confirmation
            user.username = form.cleaned_data['email']
            user.save()
            
            # Send activation email
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{request.scheme}://{current_site.domain}{reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})}"
            
            # Use EmailService to send activation email
            EmailService.send_activation_email(user, activation_link)
            
            messages.success(request, 'Please confirm your email address to complete registration.')
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def activate_account(request, uidb64, token):
    """Activate user account"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.is_email_verified = True
        user.save()
        
        # Create user profile based on user type
        UserProfile.objects.get_or_create(user=user)
        if user.user_type == 'HOUSE_OWNER':
            OwnerProfile.objects.get_or_create(user=user)
        elif user.user_type == 'TENANT':
            TenantProfile.objects.get_or_create(user=user)
        
        login(request, user)
        messages.success(request, 'Your account has been activated successfully!')
        return redirect('dashboard')
    else:
        messages.error(request, 'Activation link is invalid!')
        return redirect('accounts:login')


@login_required
def dashboard(request):
    """Main dashboard view based on user type"""
    context = {
        'user': request.user,
    }
    
    if request.user.is_superuser:
        return redirect('admin:index')
    elif request.user.user_type == 'HOUSE_OWNER':
        context['stats'] = get_owner_stats(request.user)
        return render(request, 'accounts/owner_dashboard.html', context)
    elif request.user.user_type == 'TENANT':
        context['stats'] = get_tenant_stats(request.user)
        return render(request, 'accounts/tenant_dashboard.html', context)
    else:
        return render(request, 'accounts/guest_dashboard.html', context)


def get_owner_stats(user):
    """Get statistics for owner dashboard"""
    from apps.properties.models import Property
    from apps.tenants.models import TenantApplication
    from apps.payments.models import Payment
    from apps.maintenance.models import MaintenanceRequest
    from django.db.models import Sum, Count
    
    try:
        owner = user.owner_profile
    except OwnerProfile.DoesNotExist:
        return {}
    
    # Get all properties
    properties = Property.objects.filter(owner=owner)
    
    # Calculate unit stats
    total_units = 0
    available_units = 0
    for prop in properties:
        if prop.is_multi_unit:
            total_units += prop.units.count()
            available_units += prop.units.filter(is_available=True).count()
        else:
            total_units += 1
            if prop.availability_status == 'AVAILABLE':
                available_units += 1
    
    return {
        'total_properties': properties.count(),
        'available_properties': properties.filter(availability_status='AVAILABLE').count(),
        'total_tenants': TenantApplication.objects.filter(
            property__owner=owner,
            status='APPROVED'
        ).values('tenant').distinct().count(),
        'pending_applications': TenantApplication.objects.filter(
            property__owner=owner,
            status='PENDING'
        ).count(),
        'pending_maintenance': MaintenanceRequest.objects.filter(
            property__owner=owner,
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count(),
        'total_revenue': Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'total_units': total_units,
        'available_units': available_units,
        'recent_activities': get_recent_activities(user),
    }

def get_tenant_stats(user):
    """Get statistics for tenant dashboard"""
    from apps.tenants.models import TenantApplication, Lease
    from apps.payments.models import Payment
    from apps.maintenance.models import MaintenanceRequest
    
    return {
        'active_lease': Lease.objects.filter(tenant=user, status='ACTIVE').first(),
        'applications': TenantApplication.objects.filter(tenant=user).count(),
        'pending_applications': TenantApplication.objects.filter(tenant=user, status='PENDING').count(),
        'total_payments': Payment.objects.filter(payer=user, status='COMPLETED').count(),
        'next_payment_due': get_next_payment_due(user),
        'maintenance_requests': MaintenanceRequest.objects.filter(tenant=user, status__in=['PENDING', 'IN_PROGRESS']).count(),
        'recent_notifications': user.notifications.all()[:5] if hasattr(user, 'notifications') else [],
        'recent_applications': TenantApplication.objects.filter(tenant=user)[:5],
    }


def get_recent_activities(user):
    """Get recent activities for user"""
    activities = []
    from apps.properties.models import Property
    from apps.tenants.models import TenantApplication
    
    # Recent properties added
    if user.user_type == 'HOUSE_OWNER':
        try:
            properties = Property.objects.filter(owner=user.owner_profile)[:3]
            for prop in properties:
                activities.append({
                    'description': f'Added new property: {prop.title}',
                    'icon': 'home',
                    'timestamp': prop.created_at
                })
        except:
            pass
    
    # Recent applications
    applications = TenantApplication.objects.filter(tenant=user)[:3]
    for app in applications:
        activities.append({
            'description': f'Applied for: {app.property.title}',
            'icon': 'file-signature',
            'timestamp': app.created_at
        })
    
    return sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:5]


def get_next_payment_due(user):
    """Get next payment due for tenant"""
    from apps.payments.models import Payment
    from apps.tenants.models import Lease
    
    active_lease = Lease.objects.filter(tenant=user, status='ACTIVE').first()
    if active_lease:
        next_payment = Payment.objects.filter(
            lease=active_lease,
            status='PENDING',
            due_date__gte=timezone.now()
        ).order_by('due_date').first()
        return next_payment
    return None


@login_required
def profile(request):
    """User profile view"""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def update_profile(request):
    """Update user profile"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        user.bio = request.POST.get('bio', user.bio)
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    return redirect('accounts:profile')


@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('accounts:profile')
        
        if new_password1 != new_password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('accounts:profile')
        
        if len(new_password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('accounts:profile')
        
        request.user.set_password(new_password1)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Password changed successfully!')
        return redirect('accounts:profile')
    
    return redirect('accounts:profile')


@login_required
def delete_account(request):
    """Delete user account"""
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'Account deleted successfully.')
        return redirect('home')
    return redirect('accounts:profile')


@login_required
def user_list(request):
    """List all users (admin only)"""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('dashboard')
    
    users = User.objects.all().order_by('-date_joined')
    
    # Filter by user type
    user_type = request.GET.get('user_type')
    if user_type:
        users = users.filter(user_type=user_type)
    
    # Search
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    
    return render(request, 'accounts/user_list.html', {
        'users': users_page,
        'user_type': user_type,
        'search': search,
        'user_types': User.USER_TYPES,
    })


@login_required
def user_detail(request, user_id):
    """View user details (admin only)"""
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('dashboard')
    
    user = get_object_or_404(User, id=user_id)
    return render(request, 'accounts/user_detail.html', {'user': user})


@login_required
def block_user(request, user_id):
    """Block a user (admin only)"""
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Cannot block superuser'}, status=400)
    
    user.is_active = False
    user.save()
    return JsonResponse({'status': 'success'})


@login_required
def unblock_user(request, user_id):
    """Unblock a user (admin only)"""
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    return JsonResponse({'status': 'success'})


@login_required
@user_type_required('HOUSE_OWNER')
def manage_caretakers(request):
    """Manage property caretakers"""
    try:
        owner = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        messages.error(request, 'Owner profile not found.')
        return redirect('dashboard')
    
    caretakers = User.objects.filter(
        user_type='CARETAKER',
        caretaker_profile__owner=owner
    )
    
    if request.method == 'POST':
        email = request.POST.get('email')
        permission_level = request.POST.get('permission_level', 'basic')
        
        try:
            caretaker = User.objects.get(email=email, user_type='CARETAKER')
            # Add caretaker to owner
            caretaker.caretaker_profile.owner = owner
            caretaker.caretaker_profile.permission_level = permission_level
            caretaker.caretaker_profile.save()
            messages.success(request, f'Caretaker {caretaker.get_full_name()} added successfully!')
        except User.DoesNotExist:
            messages.error(request, 'User not found or not a caretaker.')
        except AttributeError:
            messages.error(request, 'User does not have a caretaker profile.')
        
        return redirect('accounts:manage_caretakers')
    
    return render(request, 'accounts/manage_caretakers.html', {
        'caretakers': caretakers,
    })


def custom_logout(request):
    """Custom logout view"""
    if request.user.is_authenticated:
        # Log logout time
        from .models import LoginHistory
        LoginHistory.objects.filter(user=request.user, logout_time__isnull=True).update(
            logout_time=timezone.now()
        )
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


# Bank Account Setup Views

def _get_paystack_bank_choices():
    """Get the current Kenya-specific bank codes directly from Paystack."""
    from apps.payments.services import PaystackService
    response = PaystackService().list_banks(country='kenya')
    if not response.get('status'):
        return [], response.get('message', 'Unable to load banks from Paystack.')
    return [
        (bank['code'], bank['name'])
        for bank in response.get('data', [])
        if bank.get('code') and bank.get('name')
    ], None

@login_required
@owner_required
def setup_bank_account(request):
    """Setup bank account for Paystack subaccount"""
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        messages.error(request, 'Owner profile not found.')
        return redirect('dashboard')
    
    # Check if subaccount already exists
    subaccount = getattr(owner_profile, 'paystack_subaccount', None)
    bank_choices, bank_error = _get_paystack_bank_choices()
    
    if request.method == 'POST':
        form = PaystackSubaccountForm(request.POST, instance=subaccount, bank_choices=bank_choices)
        if form.is_valid():
            from apps.payments.services import PaystackService
            
            # Prepare data for Paystack
            bank_code = form.cleaned_data['bank_code']
            account_number = form.cleaned_data['account_number']
            account_name = form.cleaned_data['account_name']
            business_name = form.cleaned_data['business_name']
            
            # Create subaccount via Paystack
            paystack_service = PaystackService()
            response = paystack_service.create_subaccount(
                business_name=business_name,
                settlement_bank=bank_code,
                account_number=account_number,
                account_holder_name=account_name,
                percentage_charge=3  # 3% for Winda
            )
            
            if response.get('status') is True:
                # Save subaccount details
                if subaccount is None:
                    subaccount = form.save(commit=False)
                    subaccount.owner_profile = owner_profile
                else:
                    subaccount = form.save(commit=False)
                
                subaccount.subaccount_code = response.get('data', {}).get('subaccount_code', '')
                response_data = response.get('data', {})
                subaccount.verification_status = 'VERIFIED' if response_data.get('is_verified') else 'PENDING'
                subaccount.is_active = response_data.get('active', True)
                subaccount.paystack_response = response_data
                subaccount.save()
                
                # Update owner profile
                owner_profile.bank_account_set_up = True
                owner_profile.paystack_subaccount_verified = True
                owner_profile.save()
                
                messages.success(request, 'Bank account setup successfully! You can now receive payments.')
                return redirect('accounts:bank_account_details')
            else:
                messages.error(request, f"Failed to setup subaccount: {response.get('message', 'Unknown error')}")
    else:
        form = PaystackSubaccountForm(instance=subaccount, bank_choices=bank_choices)

    # Get bank choices for the template
    if bank_error:
        messages.warning(request, 'Paystack banks could not be loaded. Please refresh and try again.')
    
    return render(request, 'accounts/setup_bank_account.html', {
        'form': form,
        'subaccount': subaccount,
        'bank_account_set_up': owner_profile.bank_account_set_up,
        'bank_choices': bank_choices,
    })


@login_required
@owner_required
def bank_account_details(request):
    """View bank account details"""
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        messages.error(request, 'Owner profile not found.')
        return redirect('dashboard')
    
    subaccount = getattr(owner_profile, 'paystack_subaccount', None)
    
    if not subaccount:
        messages.info(request, 'Please setup your bank account first.')
        return redirect('accounts:setup_bank_account')
    
    return render(request, 'accounts/bank_account_details.html', {
        'subaccount': subaccount,
        'owner_profile': owner_profile,
    })


@login_required
@owner_required
def update_bank_account(request):
    """Update bank account details"""
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        messages.error(request, 'Owner profile not found.')
        return redirect('dashboard')
    
    subaccount = getattr(owner_profile, 'paystack_subaccount', None)
    
    if not subaccount:
        messages.error(request, 'Please setup your bank account first.')
        return redirect('accounts:setup_bank_account')

    bank_choices, bank_error = _get_paystack_bank_choices()
    
    if request.method == 'POST':
        form = PaystackSubaccountForm(request.POST, instance=subaccount, bank_choices=bank_choices)
        if form.is_valid():
            from apps.payments.services import PaystackService
            
            # Update via Paystack
            bank_code = form.cleaned_data['bank_code']
            account_number = form.cleaned_data['account_number']
            account_name = form.cleaned_data['account_name']
            business_name = form.cleaned_data['business_name']
            
            paystack_service = PaystackService()
            response = paystack_service.update_subaccount(
                subaccount_code=subaccount.subaccount_code,
                business_name=business_name,
                settlement_bank=bank_code,
                account_number=account_number,
                account_holder_name=account_name,
            )
            
            if response.get('status') is True:
                updated_subaccount = form.save(commit=False)
                response_data = response.get('data', {})
                updated_subaccount.paystack_response = response_data or updated_subaccount.paystack_response
                updated_subaccount.is_active = response_data.get('active', updated_subaccount.is_active)
                updated_subaccount.verification_status = 'VERIFIED' if response_data.get('is_verified') else 'PENDING'
                updated_subaccount.save()
                messages.success(request, 'Bank account updated successfully!')
                return redirect('accounts:bank_account_details')
            else:
                messages.error(request, f"Failed to update: {response.get('message', 'Unknown error')}")
    else:
        form = PaystackSubaccountForm(instance=subaccount, bank_choices=bank_choices)

    # Get bank choices for the template
    if bank_error:
        messages.warning(request, 'Paystack banks could not be loaded. Please refresh and try again.')
    
    return render(request, 'accounts/update_bank_account.html', {
        'form': form,
        'subaccount': subaccount,
        'bank_choices': bank_choices,
    })

@login_required
@owner_required
@require_http_methods(["POST"])
def delete_bank_account(request):
    """Delete bank account details"""
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Owner profile not found'}, status=404)
    
    subaccount = getattr(owner_profile, 'paystack_subaccount', None)
    
    if not subaccount:
        return JsonResponse({'status': 'error', 'message': 'No bank account found'}, status=404)
    
    # Deactivate in Paystack
    from apps.payments.services import PaystackService
    paystack_service = PaystackService()
    try:
        response = paystack_service.deactivate_subaccount(subaccount.subaccount_code)
    except:
        pass  # Continue with deletion even if Paystack fails
    
    # Delete from database
    subaccount.delete()
    
    # Update owner profile
    owner_profile.bank_account_set_up = False
    owner_profile.paystack_subaccount_verified = False
    owner_profile.save()
    
    messages.success(request, 'Bank account removed successfully.')
    return JsonResponse({'status': 'success'})

@login_required
def update_profile_picture(request):
    """Update profile picture via AJAX"""
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        user = request.user
        user.profile_picture = request.FILES['profile_picture']
        user.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
@owner_required
def update_business(request):
    """Update business information for owner"""
    if request.method == 'POST':
        try:
            owner_profile = request.user.owner_profile
        except OwnerProfile.DoesNotExist:
            messages.error(request, 'Owner profile not found.')
            return redirect('accounts:profile')
        
        # Update business fields
        owner_profile.company_name = request.POST.get('company_name', owner_profile.company_name)
        owner_profile.company_registration_number = request.POST.get('company_registration_number', owner_profile.company_registration_number)
        owner_profile.tax_pin = request.POST.get('tax_pin', owner_profile.tax_pin)
        
        # Handle business license upload
        if request.FILES.get('business_license'):
            owner_profile.business_license = request.FILES['business_license']
        
        owner_profile.save()
        messages.success(request, 'Business information updated successfully!')
        return redirect('accounts:profile')
    
    return redirect('accounts:profile')

@login_required
def resend_activation_email(request):
    """Resend activation email to user"""
    user = request.user
    
    if user.is_active:
        messages.info(request, 'Your account is already activated.')
        return redirect('dashboard')
    
    try:
        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_link = f"{request.scheme}://{current_site.domain}{reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})}"
        
        EmailService.send_activation_email(user, activation_link)
        messages.success(request, 'Activation email sent! Please check your inbox.')
    except Exception as e:
        messages.error(request, f'Failed to send activation email. Error: {str(e)}')
    
    return redirect('dashboard')