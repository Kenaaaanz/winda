from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    User, UserProfile, OwnerProfile, TenantProfile, 
    CaretakerProfile, LoginHistory, PaystackSubaccount,
    CaretakerPropertyAssignment
)


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
        'verification_status_display',
        'is_active_display',
        'is_email_verified_display',
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
            'fields': ('user_type', 'verification_status', 'verification_documents', 'is_email_verified', 'is_phone_verified')
        }),
        (_('Preferences'), {
            'fields': ('language', 'timezone', 'notification_preferences'),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'last_activity', 'last_login_ip', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('last_login', 'last_activity', 'last_login_ip', 'date_joined')
    
    actions = ['verify_email', 'unverify_email', 'mark_as_verified', 'mark_as_pending']
    
    def get_readonly_fields(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return self.readonly_fields + ('is_superuser', 'is_staff', 'user_type')
        return self.readonly_fields
    
    def verify_email(self, request, queryset):
        """Mark selected users as email verified"""
        updated = queryset.update(is_email_verified=True, verification_status='VERIFIED')
        self.message_user(request, f'{updated} users marked as email verified.')
    verify_email.short_description = "✅ Verify email for selected users"
    
    def unverify_email(self, request, queryset):
        """Mark selected users as email not verified"""
        updated = queryset.update(is_email_verified=False)
        self.message_user(request, f'{updated} users marked as email not verified.')
    unverify_email.short_description = "❌ Unverify email for selected users"
    
    def mark_as_verified(self, request, queryset):
        """Mark selected users as fully verified"""
        updated = queryset.update(
            is_email_verified=True,
            verification_status='VERIFIED'
        )
        self.message_user(request, f'{updated} users marked as fully verified.')
    mark_as_verified.short_description = "⭐ Mark as Verified"
    
    def mark_as_pending(self, request, queryset):
        """Mark selected users as pending verification"""
        updated = queryset.update(
            is_email_verified=False,
            verification_status='PENDING'
        )
        self.message_user(request, f'{updated} users marked as pending.')
    mark_as_pending.short_description = "⏳ Mark as Pending"
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        colors = {
            'VERIFIED': 'green',
            'PENDING': 'yellow',
            'REJECTED': 'red',
            'IN_REVIEW': 'blue',
        }
        color = colors.get(obj.verification_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            {'green': '#22c55e', 'yellow': '#eab308', 'red': '#ef4444', 'blue': '#3b82f6', 'gray': '#6b7280'}[color],
            obj.get_verification_status_display()
        )
    verification_status_display.short_description = 'Verification'
    
    def is_active_display(self, obj):
        """Display active status with color coding"""
        if obj.is_active:
            return format_html('<span style="color: #22c55e;">✓ Active</span>')
        return format_html('<span style="color: #ef4444;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'
    
    def is_email_verified_display(self, obj):
        """Display email verification status"""
        if obj.is_email_verified:
            return format_html('<span style="color: #22c55e;">✓ Verified</span>')
        return format_html('<span style="color: #eab308;">⚠ Pending</span>')
    is_email_verified_display.short_description = 'Email Verified'


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
    list_display = ('user', 'company_name', 'bank_account_status', 'paystack_subaccount_verified_display', 'total_properties', 'total_revenue_display')
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
    
    def bank_account_status(self, obj):
        """Display bank account status"""
        if obj.bank_account_set_up and obj.paystack_subaccount_verified:
            return format_html('<span style="color: #22c55e;">✓ Connected</span>')
        elif obj.bank_account_set_up:
            return format_html('<span style="color: #eab308;">⚠ Pending</span>')
        return format_html('<span style="color: #6b7280;">✗ Not Set Up</span>')
    bank_account_status.short_description = 'Bank Account'
    
    def paystack_subaccount_verified_display(self, obj):
        """Display Paystack subaccount verification status"""
        if obj.paystack_subaccount_verified:
            return format_html('<span style="color: #22c55e;">✓ Verified</span>')
        return format_html('<span style="color: #ef4444;">✗ Unverified</span>')
    paystack_subaccount_verified_display.short_description = 'Paystack Verified'
    
    def total_revenue_display(self, obj):
        """Display total revenue with formatting"""
        return f"KES {obj.total_revenue:,.2f}"
    total_revenue_display.short_description = 'Total Revenue'


@admin.register(PaystackSubaccount)
class PaystackSubaccountAdmin(admin.ModelAdmin):
    list_display = ('get_owner_name', 'account_name', 'account_number', 'bank_name', 'is_active_display', 'verification_status_display', 'created_at')
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
    
    def is_active_display(self, obj):
        """Display active status with color coding"""
        if obj.is_active:
            return format_html('<span style="color: #22c55e;">✓ Active</span>')
        return format_html('<span style="color: #ef4444;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        colors = {
            'VERIFIED': '#22c55e',
            'PENDING': '#eab308',
            'REJECTED': '#ef4444',
        }
        color = colors.get(obj.verification_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    verification_status_display.short_description = 'Status'


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employer_name', 'monthly_income_display', 'is_approved_display')
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
    
    def monthly_income_display(self, obj):
        if obj.monthly_income:
            return f"KES {obj.monthly_income:,.2f}"
        return "-"
    monthly_income_display.short_description = 'Monthly Income'
    
    def is_approved_display(self, obj):
        if obj.is_approved:
            return format_html('<span style="color: #22c55e;">✓ Approved</span>')
        return format_html('<span style="color: #eab308;">⏳ Pending</span>')
    is_approved_display.short_description = 'Approved'


@admin.register(CaretakerProfile)
class CaretakerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'owner', 'permission_level_display', 'is_active_display', 'assigned_properties_count', 'created_at')
    list_filter = ('permission_level', 'is_active', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'owner__company_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('user', 'owner')}),
        (_('Permissions'), {'fields': ('permission_level',)}),
        (_('Status'), {'fields': ('is_active',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def permission_level_display(self, obj):
        """Display permission level with color coding"""
        colors = {
            'FULL': '#22c55e',
            'STANDARD': '#3b82f6',
            'BASIC': '#6b7280',
        }
        color = colors.get(obj.permission_level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_permission_level_display()
        )
    permission_level_display.short_description = 'Permission Level'
    
    def is_active_display(self, obj):
        """Display active status with color coding"""
        if obj.is_active:
            return format_html('<span style="color: #22c55e;">✓ Active</span>')
        return format_html('<span style="color: #ef4444;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'
    
    def assigned_properties_count(self, obj):
        """Get count of assigned properties with link"""
        count = obj.get_assigned_properties().count()
        if count > 0:
            return format_html(
                '<a href="{}?caretaker__id={}" style="color: #3b82f6;">{} properties</a>',
                reverse('admin:accounts_caretakerpropertyassignment_changelist'),
                obj.id,
                count
            )
        return "0"
    assigned_properties_count.short_description = 'Assigned Properties'


@admin.register(CaretakerPropertyAssignment)
class CaretakerPropertyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('caretaker', 'property', 'assigned_at_display', 'is_active_display')
    list_filter = ('is_active', 'assigned_at')
    search_fields = ('caretaker__user__email', 'property__title')
    readonly_fields = ('assigned_at',)
    
    fieldsets = (
        (None, {'fields': ('caretaker', 'property')}),
        (_('Status'), {'fields': ('is_active',)}),
        (_('Timestamps'), {'fields': ('assigned_at',), 'classes': ('collapse',)}),
    )
    
    def assigned_at_display(self, obj):
        return obj.assigned_at.strftime('%Y-%m-%d %H:%M')
    assigned_at_display.short_description = 'Assigned At'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #22c55e;">✓ Active</span>')
        return format_html('<span style="color: #ef4444;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time_display', 'ip_address', 'device_type', 'is_suspicious_display')
    list_filter = ('is_suspicious', 'device_type', 'login_time')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('user', 'login_time', 'logout_time', 'ip_address', 'user_agent', 'device_type', 'location')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def login_time_display(self, obj):
        return obj.login_time.strftime('%Y-%m-%d %H:%M')
    login_time_display.short_description = 'Login Time'
    
    def is_suspicious_display(self, obj):
        if obj.is_suspicious:
            return format_html('<span style="color: #ef4444;">⚠ Suspicious</span>')
        return format_html('<span style="color: #22c55e;">✓ Normal</span>')
    is_suspicious_display.short_description = 'Suspicious'