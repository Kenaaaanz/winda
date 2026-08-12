# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile, OwnerProfile, TenantProfile, CaretakerProfile, LoginHistory, PaystackSubaccount


class CustomUserChangeForm(UserChangeForm):
    """Custom form for changing user in admin"""
    class Meta:
        model = User
        fields = '__all__'


class CustomUserCreationForm(UserCreationForm):
    """Custom form for creating user in admin"""
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'user_type')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = (
        'email', 
        'first_name', 
        'last_name', 
        'user_type', 
        'verification_status', 
        'is_active',
        'is_email_verified',
        'date_joined'
    )
    list_filter = (
        'user_type', 
        'verification_status', 
        'is_active', 
        'is_email_verified',
        'is_superuser',
        'date_joined'
    )
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone', 'user_type', 'password1', 'password2'),
        }),
    )
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name', 'phone', 'bio', 'profile_picture')
        }),
        (_('User Type & Verification'), {
            'fields': ('user_type', 'verification_status', 'verification_documents')
        }),
        (_('Preferences'), {
            'fields': ('language', 'timezone', 'notification_preferences'),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'last_activity', 'last_login_ip'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('last_login', 'last_activity', 'last_login_ip', 'date_joined')
    
    def get_readonly_fields(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return self.readonly_fields + ('is_superuser', 'is_staff', 'user_type')
        return self.readonly_fields


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'country', 'preferred_contact_method')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user',)
    
    fieldsets = (
        (None, {'fields': ('user',)}),
        (_('Address'), {'fields': ('address', 'city', 'country', 'postal_code')}),
        (_('Business Info'), {'fields': ('business_name', 'business_registration', 'tax_id')}),
        (_('Emergency Contact'), {'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation')}),
        (_('Preferences'), {'fields': ('preferred_contact_method', 'marketing_opt_in')}),
    )


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'bank_account_set_up', 'paystack_subaccount_verified', 'total_properties', 'total_revenue')
    list_filter = ('bank_account_set_up', 'paystack_subaccount_verified', 'created_at')
    search_fields = ('user__email', 'company_name', 'tax_pin')
    readonly_fields = ('total_revenue', 'platform_fees_paid', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('user', 'company_name')}),
        (_('Business Details'), {'fields': ('company_registration_number', 'tax_pin', 'business_license')}),
        (_('Bank Account Setup'), {'fields': ('bank_account_set_up', 'paystack_subaccount_verified')}),
        (_('Statistics'), {'fields': ('total_properties', 'total_tenants', 'total_revenue', 'platform_fees_paid', 'average_rating')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(PaystackSubaccount)
class PaystackSubaccountAdmin(admin.ModelAdmin):
    list_display = ('get_owner_name', 'account_name', 'account_number', 'is_active', 'verification_status', 'created_at')
    list_filter = ('is_active', 'verification_status', 'created_at')
    search_fields = ('account_name', 'business_name', 'subaccount_code', 'owner_profile__user__email')
    readonly_fields = ('subaccount_code', 'paystack_response', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('Owner Information'), {'fields': ('owner_profile',)}),
        (_('Bank Details'), {'fields': ('bank_code', 'account_number', 'account_name', 'business_name')}),
        (_('Paystack Information'), {'fields': ('subaccount_code', 'percentage_charge', 'verification_status', 'is_active')}),
        (_('Metadata'), {'fields': ('paystack_response', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_owner_name(self, obj):
        return obj.owner_profile.user.get_full_name() or obj.owner_profile.user.email
    get_owner_name.short_description = 'Owner'


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employer_name', 'monthly_income', 'is_approved')
    list_filter = ('is_approved',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'employer_name')
    
    fieldsets = (
        (None, {'fields': ('user',)}),
        (_('Employment'), {'fields': ('employer_name', 'employer_contact', 'job_title', 'monthly_income')}),
        (_('Guarantor'), {'fields': ('guarantor_name', 'guarantor_phone', 'guarantor_email', 'guarantor_relationship')}),
        (_('Rental History'), {'fields': ('previous_rental_address', 'previous_landlord_name', 'previous_landlord_phone', 'previous_rental_duration')}),
        (_('Documents'), {'fields': ('national_id', 'passport_photo', 'employment_letter', 'bank_statement')}),
        (_('References'), {'fields': ('reference_name', 'reference_phone', 'reference_email')}),
        (_('Status'), {'fields': ('is_approved', 'approved_at')}),
    )


@admin.register(CaretakerProfile)
class CaretakerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'owner', 'permission_level', 'is_active')
    list_filter = ('permission_level', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'owner__company_name')
    filter_horizontal = ('assigned_properties',)
    
    fieldsets = (
        (None, {'fields': ('user', 'owner')}),
        (_('Permissions'), {'fields': ('permission_level', 'assigned_properties')}),
        (_('Status'), {'fields': ('is_active',)}),
    )


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'ip_address', 'device_type', 'is_suspicious')
    list_filter = ('is_suspicious', 'device_type', 'login_time')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('user', 'login_time', 'logout_time', 'ip_address', 'user_agent', 'device_type', 'location')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False