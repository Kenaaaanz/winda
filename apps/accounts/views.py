import json
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
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import models
from django.views.decorators.http import require_http_methods
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.db import transaction

from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler
from apps.notifications.models import Notification
from apps.properties.models import Property

from .models import CaretakerProfile, CaretakerPropertyAssignment, User, UserProfile, OwnerProfile, TenantProfile, LoginHistory
from .forms import (
    CaretakerInviteForm, CaretakerUpdateForm, PaystackSubaccountForm, 
    UserRegistrationForm, UserLoginForm, UserProfileForm,
    OwnerProfileForm, TenantProfileForm, UserUpdateForm,
    CustomPasswordChangeForm, PasswordResetForm,
    RegistrationStep1Form, RegistrationStep2Form, RegistrationStep3Form
)
from .tokens import account_activation_token
from .decorators import user_type_required, owner_required, tenant_required
from apps.emails.utils import EmailService


# ==================== NEW REGISTRATION WIZARD ====================

def register_wizard(request):
    """Registration wizard for owners and tenants"""
    # If user is already logged in, redirect
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Get current step from session or default to 1
    step = request.session.get('registration_step', 1)
    user_type = request.session.get('registration_user_type', None)
    
    # If no user_type is set, show the type selection page
    if not user_type:
        if request.method == 'POST':
            user_type = request.POST.get('user_type')
            if user_type in ['TENANT', 'HOUSE_OWNER']:
                request.session['registration_user_type'] = user_type
                request.session['registration_step'] = 1
                return redirect('accounts:register')
            else:
                messages.error(request, 'Please select a user type.')
                return render(request, 'accounts/register_type_select.html')
        return render(request, 'accounts/register_type_select.html')
    
    # Handle user type change via GET parameter
    if request.method == 'GET' and 'type' in request.GET:
        user_type = request.GET.get('type')
        if user_type in ['TENANT', 'HOUSE_OWNER']:
            request.session['registration_user_type'] = user_type
            request.session['registration_step'] = 1
            return redirect('accounts:register')
    
    # Step 1: Basic Information
    if step == 1:
        if request.method == 'POST':
            form = RegistrationStep1Form(request.POST)
            if form.is_valid():
                # Store data in session - convert phone to string
                request.session['registration_data'] = {
                    'email': form.cleaned_data['email'],
                    'first_name': form.cleaned_data['first_name'],
                    'last_name': form.cleaned_data['last_name'],
                    'phone': str(form.cleaned_data['phone']),
                    'password': form.cleaned_data['password1'],
                }
                
                # If tenant, create account and redirect to dashboard
                if user_type == 'TENANT':
                    return create_tenant_account(request)
                
                # If owner, go to step 2
                request.session['registration_step'] = 2
                return redirect('accounts:register')
        else:
            form = RegistrationStep1Form()
        
        return render(request, 'accounts/register_wizard_step1.html', {
            'form': form,
            'user_type': user_type,
            'step': step,
            'total_steps': 3 if user_type == 'HOUSE_OWNER' else 1,
        })
    
    # Step 2: Business Details (Owner only)
    if step == 2 and user_type == 'HOUSE_OWNER':
        if request.method == 'POST':
            form = RegistrationStep2Form(request.POST, request.FILES)
            if form.is_valid():
                # Store business data WITHOUT the file
                request.session['registration_business_data'] = {
                    'company_name': form.cleaned_data['company_name'],
                    'company_registration_number': form.cleaned_data.get('company_registration_number', ''),
                    'tax_pin': form.cleaned_data.get('tax_pin', ''),
                }
                
                # Store the file in a temporary location or in memory
                # Option 1: Store in request.FILES and pass to next step
                if request.FILES.get('business_license'):
                    # Store the file in the session using its name and content
                    # But we'll handle it differently - store in a temporary variable
                    request.session['has_business_license'] = True
                    # Store the file temporarily (we'll process it in create_owner_account)
                    request._business_license_file = request.FILES['business_license']
                
                request.session['registration_step'] = 3
                return redirect('accounts:register')
        else:
            form = RegistrationStep2Form()
        
        return render(request, 'accounts/register_wizard_step2.html', {
            'form': form,
            'user_type': user_type,
            'step': step,
            'total_steps': 3,
        })
    
    # Step 3: Bank Details (Owner only) - Use existing template
    if step == 3 and user_type == 'HOUSE_OWNER':
        # Get bank choices from Paystack
        from .views import _get_paystack_bank_choices
        bank_choices, bank_error = _get_paystack_bank_choices()
        
        if request.method == 'POST':
            # Use the imported PaystackSubaccountForm (no need to import again)
            form = PaystackSubaccountForm(request.POST, bank_choices=bank_choices)
            if form.is_valid():
                # Store bank data in session
                request.session['registration_bank_data'] = {
                    'bank_code': form.cleaned_data['bank_code'],
                    'account_number': form.cleaned_data['account_number'],
                    'account_name': form.cleaned_data['account_name'],
                    'business_name': form.cleaned_data['business_name'],
                }
                return create_owner_account(request)
            else:
                # Re-render with errors using the existing template
                return render(request, 'accounts/setup_bank_account.html', {
                    'form': form,
                    'bank_choices': bank_choices,
                    'bank_error': bank_error,
                    'is_wizard': True,
                })
        else:
            # GET request - show the existing bank account template
            initial_data = {}
            if 'registration_bank_data' in request.session:
                bank_data = request.session.get('registration_bank_data', {})
                initial_data = {
                    'bank_code': bank_data.get('bank_code', ''),
                    'account_number': bank_data.get('account_number', ''),
                    'account_name': bank_data.get('account_name', ''),
                    'business_name': bank_data.get('business_name', ''),
                }
            
            form = PaystackSubaccountForm(initial=initial_data, bank_choices=bank_choices)
            
            return render(request, 'accounts/setup_bank_account.html', {
                'form': form,
                'bank_choices': bank_choices,
                'bank_error': bank_error,
                'is_wizard': True,
            })
        
    # Fallback - reset if something goes wrong
    request.session.pop('registration_step', None)
    request.session.pop('registration_user_type', None)
    messages.warning(request, 'Please start the registration process again.')
    return redirect('accounts:register')

def create_tenant_account(request):
    """Create tenant account (auto-approved)"""
    data = request.session.get('registration_data', {})
    
    with transaction.atomic():
        # Check if user already exists
        user = None
        try:
            user = User.objects.get(email=data['email'])
            # If user exists but is inactive, reactivate
            if not user.is_active:
                user.is_active = True
                user.is_email_verified = True
                user.verification_status = 'VERIFIED'
                user.user_type = 'TENANT'
                user.phone = data.get('phone', '')  # Phone is already a string
                user.save()
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                password=data['password'],
                user_type='TENANT',
                is_active=True,
                is_email_verified=True,
                verification_status='VERIFIED',
            )
            # Set phone separately - it's already a string
            user.phone = data.get('phone', '')
            user.save()
        
        # Create user profile if it doesn't exist
        UserProfile.objects.get_or_create(user=user)
        
        # Create tenant profile if it doesn't exist
        TenantProfile.objects.get_or_create(user=user)
        
        # Clear session
        request.session.pop('registration_data', None)
        request.session.pop('registration_step', None)
        request.session.pop('registration_user_type', None)
        
        # Log user in
        login(request, user)
        
        messages.success(request, 'Account created successfully! Welcome to Winda.')
        return redirect('dashboard')
    
def create_owner_account(request):
    """Create owner account (pending admin approval)"""
    data = request.session.get('registration_data', {})
    business_data = request.session.get('registration_business_data', {})
    bank_data = request.session.get('registration_bank_data', {})
    
    # Get the business license file from the request
    business_license_file = getattr(request, '_business_license_file', None)
    
    with transaction.atomic():
        # Check if user already exists
        user = None
        try:
            user = User.objects.get(email=data['email'])
            # Update existing user
            if not user.is_active:
                user.is_active = True
            user.user_type = 'HOUSE_OWNER'
            user.is_email_verified = False
            user.verification_status = 'PENDING'
            user.phone = data.get('phone', '')
            user.save()
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                password=data['password'],
                user_type='HOUSE_OWNER',
                is_active=True,
                is_email_verified=False,
                verification_status='PENDING',
            )
            user.phone = data.get('phone', '')
            user.save()
        
        # Create user profile if it doesn't exist
        UserProfile.objects.get_or_create(user=user)
        
        # Create owner profile if it doesn't exist
        owner_profile, created = OwnerProfile.objects.get_or_create(
            user=user,
            defaults={
                'company_name': business_data.get('company_name', ''),
                'company_registration_number': business_data.get('company_registration_number', ''),
                'tax_pin': business_data.get('tax_pin', ''),
            }
        )
        
        # If owner profile already exists, update it
        if not created:
            owner_profile.company_name = business_data.get('company_name', owner_profile.company_name)
            owner_profile.company_registration_number = business_data.get('company_registration_number', owner_profile.company_registration_number)
            owner_profile.tax_pin = business_data.get('tax_pin', owner_profile.tax_pin)
            owner_profile.save()
        
        # Handle business license file upload
        if business_license_file:
            from apps.common.utils.cloudinary_utils import CloudinaryService
            result = CloudinaryService.upload_document(business_license_file, f'business_licenses/{user.id}')
            if result:
                owner_profile.business_license = result['secure_url']
                owner_profile.save()
        
        # Create bank account using the data from session
        try:
            from apps.payments.models import PaystackSubaccount
            # Check if bank account already exists
            bank_account = PaystackSubaccount.objects.filter(owner_profile=owner_profile).first()
            if not bank_account:
                PaystackSubaccount.objects.create(
                    owner_profile=owner_profile,
                    bank_code=bank_data.get('bank_code', ''),
                    account_number=bank_data.get('account_number', ''),
                    account_name=bank_data.get('account_name', ''),
                    business_name=bank_data.get('business_name', business_data.get('company_name', '')),
                    verification_status='PENDING',
                    is_active=False,
                )
            else:
                # Update existing bank account
                bank_account.bank_code = bank_data.get('bank_code', bank_account.bank_code)
                bank_account.account_number = bank_data.get('account_number', bank_account.account_number)
                bank_account.account_name = bank_data.get('account_name', bank_account.account_name)
                bank_account.business_name = bank_data.get('business_name', bank_account.business_name)
                bank_account.save()
        except Exception as e:
            print(f"Bank account creation error: {e}")
        
        # Notify admins
        notify_admins_new_owner(user)
        
        # Clear session
        request.session.pop('registration_data', None)
        request.session.pop('registration_business_data', None)
        request.session.pop('registration_bank_data', None)
        request.session.pop('registration_step', None)
        request.session.pop('registration_user_type', None)
        request.session.pop('has_business_license', None)
        
        # Clear the temporary file
        if hasattr(request, '_business_license_file'):
            delattr(request, '_business_license_file')
        
        messages.success(
            request,
            'Your account has been created! Your application is pending admin approval. '
            'You will receive a notification once your account is verified.'
        )
        return redirect('accounts:owner_pending_approval')
            
def notify_admins_new_owner(user):
    """Notify admins about new owner registration"""
    from apps.notifications.models import Notification
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    admins = User.objects.filter(is_superuser=True)
    for admin in admins:
        Notification.objects.create(
            user=admin,
            notification_type='SYSTEM',
            title='New Owner Registration Pending',
            message=f'{user.get_full_name()} has registered as a property owner and is awaiting approval.',
            related_object_type='user',
            related_object_id=str(user.id),
            data={
                'user_id': str(user.id),
                'user_email': user.email,
                'user_name': user.get_full_name()
            }
        )


@login_required
def owner_pending_approval(request):
    """Show pending approval page for owners"""
    if request.user.user_type != 'HOUSE_OWNER':
        return redirect('dashboard')
    
    if request.user.verification_status == 'VERIFIED':
        return redirect('dashboard')
    
    return render(request, 'accounts/owner_pending_approval.html', {
        'user': request.user,
    })


@staff_member_required
def admin_verify_owners(request):
    """Admin view to verify pending owners"""
    pending_owners = User.objects.filter(
        user_type='HOUSE_OWNER',
        verification_status='PENDING'
    ).select_related('owner_profile')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        user = get_object_or_404(User, id=user_id, user_type='HOUSE_OWNER')
        
        if action == 'approve':
            user.verification_status = 'VERIFIED'
            user.is_email_verified = True
            user.verified_at = timezone.now()
            user.verified_by = request.user
            user.admin_notes = notes
            user.save()
            
            # Notify owner
            Notification.objects.create(
                user=user,
                notification_type='SYSTEM',
                title='Account Approved! 🎉',
                message=f'Your account has been verified by admin. You can now list properties on Winda.',
                related_object_type='user',
                related_object_id=str(user.id)
            )
            
            messages.success(request, f'{user.get_full_name()} has been approved.')
            
        elif action == 'reject':
            user.verification_status = 'REJECTED'
            user.admin_notes = notes
            user.verified_at = timezone.now()
            user.verified_by = request.user
            user.save()
            
            Notification.objects.create(
                user=user,
                notification_type='SYSTEM',
                title='Account Rejected',
                message=f'Your account application has been rejected. Reason: {notes}',
                related_object_type='user',
                related_object_id=str(user.id)
            )
            
            messages.success(request, f'{user.get_full_name()} has been rejected.')
        
        return redirect('accounts:admin_verify_owners')
    
    return render(request, 'accounts/admin_verify_owners.html', {
        'pending_owners': pending_owners,
    })

def get_property_model():
    from apps.properties.models import Property
    return Property

class CustomLoginView(LoginView):
    """Custom login view that redirects based on user type"""
    template_name = 'accounts/login.html'
    
    def form_valid(self, form):
        """If the form is valid, redirect to the appropriate dashboard"""
        response = super().form_valid(form)
        user = form.get_user()
        
        # Log login history
        try:
            LoginHistory.objects.create(
                user=user,
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:255],
                device_type=self.get_device_type(self.request),
            )
        except:
            pass
        
        # Redirect based on user type
        if user.user_type == 'CARETAKER':
            return redirect('accounts:caretaker_dashboard')
        elif user.user_type == 'HOUSE_OWNER':
            return redirect('dashboard')
        elif user.user_type == 'TENANT':
            return redirect('dashboard')
        else:
            return redirect('dashboard')
    
    def get_device_type(self, request):
        """Determine device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'mobile' in user_agent:
            return 'Mobile'
        elif 'tablet' in user_agent:
            return 'Tablet'
        else:
            return 'Desktop'
    
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password. Please try again.')
        return super().form_invalid(form)

    
@login_required
def dashboard(request):
    """Main dashboard view based on user type"""
    user = request.user
    
    # Check if user is a caretaker
    if user.user_type == 'CARETAKER':
        return redirect('accounts:caretaker_dashboard')
    
    # Check if user is super admin
    if user.is_superuser:
        return redirect('admin:index')
    
    # Owner dashboard
    if user.user_type == 'HOUSE_OWNER':
        context = {
            'user': user,
            'stats': get_owner_stats(user)
        }
        return render(request, 'accounts/owner_dashboard.html', context)
    
    # Tenant dashboard
    if user.user_type == 'TENANT':
        context = {
            'user': user,
            'stats': get_tenant_stats(user)
        }
        return render(request, 'accounts/tenant_dashboard.html', context)
    
    # Guest or unknown user type
    return render(request, 'accounts/guest_dashboard.html', {'user': user})


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
    """Update profile picture using Cloudinary"""
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        user = request.user
        
        # Delete old profile picture from Cloudinary
        if user.profile_picture:
            try:
                public_id = user.profile_picture.name
                CloudinaryService.delete_image(public_id)
            except:
                pass
        
        # Upload new profile picture
        file = request.FILES['profile_picture']
        compressed = CloudinaryImageHandler.compress_image(file, max_size=(400, 400))
        result = CloudinaryService.upload_profile_picture(compressed, str(user.id))
        
        if result:
            user.profile_picture = result['secure_url']
            user.save()
            return JsonResponse({'status': 'success', 'url': result['secure_url']})
        
        return JsonResponse({'status': 'error', 'message': 'Upload failed'}, status=400)
    
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

@login_required
@owner_required
def caretaker_list(request):
    """List all caretakers for the owner - Simple template with AJAX"""
    return render(request, 'accounts/manage_caretakers.html')

@login_required
@owner_required
def caretaker_api_list(request):
    """API endpoint to get caretakers data"""
    owner = request.user.owner_profile
    caretakers = CaretakerProfile.objects.filter(owner=owner).select_related('user')
    
    data = []
    for caretaker in caretakers:
        data.append({
            'id': str(caretaker.id),  # This will be the actual ID (like '8')
            'user': {
                'id': str(caretaker.user.id),
                'full_name': caretaker.user.get_full_name() or caretaker.user.email,
                'email': caretaker.user.email,
                'profile_picture': caretaker.user.profile_picture.url if caretaker.user.profile_picture else None,
                'is_email_verified': caretaker.user.is_email_verified,
            },
            'permission_level': caretaker.permission_level,
            'permission_display': caretaker.get_permission_level_display(),
            'assigned_properties_count': caretaker.get_assigned_properties().count(),
            'is_active': caretaker.is_active,
            'created_at': caretaker.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({
        'caretakers': data,
        'stats': {
            'total': len(data),
            'active': sum(1 for c in data if c['is_active']),
        }
    })

@login_required
@owner_required
def caretaker_invite(request):
    """Invite a new caretaker"""
    owner = request.user.owner_profile
    
    if request.method == 'POST':
        form = CaretakerInviteForm(request.POST, owner=owner)
        if form.is_valid():
            email = form.cleaned_data['email']
            permission_level = form.cleaned_data['permission_level']
            assigned_properties = form.cleaned_data.get('assigned_properties', [])
            
            # Check if user exists
            try:
                user = User.objects.get(email=email)
                if user.user_type != 'CARETAKER':
                    user.user_type = 'CARETAKER'
                    user.save()
                if not user.is_email_verified:
                    user.is_email_verified = True
                    user.verification_status = 'VERIFIED'
                    user.save()
            except User.DoesNotExist:
                import random
                import string
                temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                
                user = User.objects.create_user(
                    email=email,
                    username=email,
                    password=temp_password,
                    first_name=email.split('@')[0].title(),
                    user_type='CARETAKER',
                    is_active=True,
                    is_email_verified=True,
                    verification_status='VERIFIED'
                )
                
                # Send welcome email
                from django.core.mail import send_mail
                send_mail(
                    'You have been invited as a Caretaker on Winda',
                    f'You have been invited as a caretaker on Winda.\n\n'
                    f'Your temporary password is: {temp_password}\n'
                    f'Please login and change your password.\n\n'
                    f'Login at: https://winda.co.ke/accounts/login/',
                    'noreply@winda.co.ke',
                    [email],
                    fail_silently=True
                )
            
            # Check if caretaker profile already exists
            caretaker_profile, created = CaretakerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'owner': owner,
                    'permission_level': permission_level,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing profile
                caretaker_profile.owner = owner
                caretaker_profile.permission_level = permission_level
                caretaker_profile.is_active = True
                caretaker_profile.save()
            
            # Clear existing assignments
            CaretakerPropertyAssignment.objects.filter(caretaker=caretaker_profile).delete()
            
            # Assign properties
            for property_obj in assigned_properties:
                CaretakerPropertyAssignment.objects.create(
                    caretaker=caretaker_profile,
                    property=property_obj,
                    is_active=True
                )
            
            # Send notification
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=user,
                notification_type='SYSTEM',
                title='Caretaker Invitation',
                message=f'You have been added as a caretaker for {owner.company_name}.',
                data={
                    'owner_id': str(owner.id),
                    'permission_level': permission_level
                }
            )
            
            messages.success(request, f'Caretaker {user.get_full_name()} added successfully!')
            return redirect('accounts:caretaker_list')
    else:
        form = CaretakerInviteForm(owner=owner)
    
    return render(request, 'accounts/caretaker_invite.html', {
        'form': form,
    })


@login_required
@owner_required
@require_http_methods(["POST"])
def caretaker_api_delete(request):
    """API endpoint to delete a caretaker"""
    try:
        data = json.loads(request.body)
        caretaker_id = data.get('caretaker_id')
        
        owner = request.user.owner_profile
        caretaker = CaretakerProfile.objects.get(id=caretaker_id, owner=owner)
        user = caretaker.user
        caretaker.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Caretaker {user.get_full_name()} removed successfully'
        })
    except CaretakerProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Caretaker not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
@owner_required
@require_http_methods(["POST"])
def caretaker_api_update(request):
    """API endpoint to update caretaker permissions"""
    try:
        data = json.loads(request.body)
        caretaker_id = data.get('caretaker_id')
        permission_level = data.get('permission_level')
        is_active = data.get('is_active')
        assigned_properties = data.get('assigned_properties', [])
        
        owner = request.user.owner_profile
        caretaker = CaretakerProfile.objects.get(id=caretaker_id, owner=owner)
        
        # Update permission level
        if permission_level:
            caretaker.permission_level = permission_level
            caretaker.save()
        
        # Update active status
        if is_active is not None:
            caretaker.is_active = is_active
            caretaker.save()
        
        # Update property assignments
        if assigned_properties is not None:
            # Clear existing assignments
            CaretakerPropertyAssignment.objects.filter(caretaker=caretaker).delete()
            
            # Add new assignments
            for prop_id in assigned_properties:
                from apps.properties.models import Property
                try:
                    property_obj = Property.objects.get(id=prop_id, owner=owner)
                    CaretakerPropertyAssignment.objects.create(
                        caretaker=caretaker,
                        property=property_obj,
                        is_active=True
                    )
                except Property.DoesNotExist:
                    pass
        
        return JsonResponse({
            'status': 'success',
            'message': f'Caretaker {caretaker.user.get_full_name()} updated successfully',
            'data': {
                'id': str(caretaker.id),
                'permission_level': caretaker.permission_level,
                'permission_display': caretaker.get_permission_level_display(),
                'is_active': caretaker.is_active,
                'assigned_properties_count': caretaker.get_assigned_properties().count(),
            }
        })
    except CaretakerProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Caretaker not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def caretaker_dashboard(request):
    """Dashboard for caretakers"""
    # Check if user is a caretaker
    if request.user.user_type != 'CARETAKER':
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('dashboard')
    
    try:
        caretaker_profile = request.user.caretaker_profile
    except CaretakerProfile.DoesNotExist:
        messages.error(request, 'Caretaker profile not found. Please contact your administrator.')
        return redirect('dashboard')
    
    # Check if caretaker is active
    if not caretaker_profile.is_active:
        messages.error(request, 'Your caretaker account has been deactivated. Please contact your administrator.')
        return redirect('dashboard')
    
    # Get assigned properties
    if caretaker_profile.permission_level == 'FULL':
        properties = Property.objects.filter(owner=caretaker_profile.owner)
    else:
        properties = caretaker_profile.get_assigned_properties()
    
    # Get maintenance requests
    from apps.maintenance.models import MaintenanceRequest
    maintenance_requests = MaintenanceRequest.objects.filter(
        property__in=properties
    ).order_by('-created_at')[:10]
    
    # Get pending maintenance
    pending_maintenance = MaintenanceRequest.objects.filter(
        property__in=properties,
        status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED']
    ).count()
    
    # Get total units managed
    total_units = 0
    for prop in properties:
        if prop.is_multi_unit:
            total_units += prop.units.count()
        else:
            total_units += 1
    
    context = {
        'caretaker_profile': caretaker_profile,
        'properties': properties,
        'property_count': properties.count(),
        'total_units': total_units,
        'maintenance_requests': maintenance_requests,
        'pending_maintenance': pending_maintenance,
    }
    
    return render(request, 'accounts/caretaker_dashboard.html', context)

@login_required
@owner_required
def caretaker_edit(request, caretaker_id):
    """Edit caretaker permissions - handles both UUID and integer IDs"""
    from django.contrib import messages
    from django.shortcuts import redirect, render
    import uuid
    
    try:
        owner = request.user.owner_profile
        
        # Try to find by ID (works for both UUID and integer)
        try:
            # Try as integer first
            caretaker = CaretakerProfile.objects.get(id=int(caretaker_id), owner=owner)
        except (ValueError, TypeError):
            # Try as UUID string
            try:
                caretaker = CaretakerProfile.objects.get(id=caretaker_id, owner=owner)
            except (ValueError, TypeError):
                # Try by user email as last resort
                caretaker = CaretakerProfile.objects.get(user__email=caretaker_id, owner=owner)
                
    except CaretakerProfile.DoesNotExist:
        messages.error(request, f'Caretaker not found. Please re-invite the caretaker.')
        return redirect('accounts:caretaker_list')
    except Exception as e:
        messages.error(request, f'Error finding caretaker: {str(e)}')
        return redirect('accounts:caretaker_list')
    
    if request.method == 'POST':
        form = CaretakerUpdateForm(request.POST, instance=caretaker, owner=owner)
        if form.is_valid():
            caretaker = form.save()
            
            # Update property assignments
            assigned_properties = form.cleaned_data.get('assigned_properties', [])
            
            # Clear existing assignments and add new ones
            CaretakerPropertyAssignment.objects.filter(caretaker=caretaker).delete()
            
            for property_obj in assigned_properties:
                CaretakerPropertyAssignment.objects.create(
                    caretaker=caretaker,
                    property=property_obj,
                    is_active=True
                )
            
            messages.success(request, f'Caretaker {caretaker.user.get_full_name()} updated successfully!')
            return redirect('accounts:caretaker_list')
    else:
        form = CaretakerUpdateForm(instance=caretaker, owner=owner)
        # Pre-populate assigned properties
        form.fields['assigned_properties'].initial = caretaker.get_assigned_properties()
    
    return render(request, 'accounts/caretaker_edit.html', {
        'form': form,
        'caretaker': caretaker,
    })

@login_required
@owner_required
def caretaker_delete(request, caretaker_id):
    """Remove a caretaker - handles both UUID and integer IDs"""
    from django.contrib import messages
    from django.shortcuts import redirect, render
    
    try:
        owner = request.user.owner_profile
        
        # Try to find by ID (works for both UUID and integer)
        try:
            # Try as integer first
            caretaker = CaretakerProfile.objects.get(id=int(caretaker_id), owner=owner)
        except (ValueError, TypeError):
            # Try as UUID string
            try:
                caretaker = CaretakerProfile.objects.get(id=caretaker_id, owner=owner)
            except (ValueError, TypeError):
                # Try by user email as last resort
                caretaker = CaretakerProfile.objects.get(user__email=caretaker_id, owner=owner)
                
    except CaretakerProfile.DoesNotExist:
        messages.error(request, 'Caretaker not found.')
        return redirect('accounts:caretaker_list')
    except Exception as e:
        messages.error(request, f'Error finding caretaker: {str(e)}')
        return redirect('accounts:caretaker_list')
    
    if request.method == 'POST':
        user = caretaker.user
        caretaker.delete()
        messages.success(request, f'Caretaker {user.get_full_name()} removed successfully!')
        return redirect('accounts:caretaker_list')
    
    return render(request, 'accounts/caretaker_delete.html', {
        'caretaker': caretaker,
    })