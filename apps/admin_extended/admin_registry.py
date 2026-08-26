from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# Import the admin_site from admin.py
from .admin import admin_site

# Import ALL models from all apps
from apps.accounts.models import User, OwnerProfile, TenantProfile, CaretakerProfile
from apps.properties.models import Property, Unit, PropertyImage, PropertyDocument
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment, Invoice, SubscriptionPlan
from apps.maintenance.models import MaintenanceRequest, MaintenanceTask
from apps.communications.models import ChatRoom, Message, MessageTemplate
from apps.analytics.models import AnalyticsEvent, AnalyticsMetric, SavedReport
from apps.notifications.models import Notification, NotificationPreference
from apps.seo.models import SeoMeta, SeoRobots, SeoSitemap, SeoRedirect

# Try to import legal models if they exist
try:
    from apps.legal.models import TermsOfService, PrivacyPolicy
    LEGAL_MODELS_AVAILABLE = True
except ImportError:
    LEGAL_MODELS_AVAILABLE = False


# ========================================
# ACCOUNTS APP REGISTRATIONS
# ========================================

@admin.register(User, site=admin_site)
class CustomUserAdmin(UserAdmin):
    """Custom User admin with status badges"""
    list_display = ('email', 'full_name', 'user_type_badge', 'verification_badge', 'is_active', 'date_joined')
    list_filter = ('user_type', 'verification_status', 'is_active', 'is_email_verified')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'bio', 'profile_picture')}),
        ('User Type', {'fields': ('user_type',)}),
        ('Verification', {'fields': ('verification_status', 'verification_documents')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    def full_name(self, obj):
        return obj.get_full_name() or obj.email
    full_name.short_description = 'Full Name'
    
    def user_type_badge(self, obj):
        colors = {
            'SUPER_ADMIN': 'red',
            'HOUSE_OWNER': 'blue',
            'TENANT': 'green',
            'CARETAKER': 'yellow',
            'GUEST': 'gray',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.user_type, 'gray'),
            obj.get_user_type_display()
        )
    user_type_badge.short_description = 'User Type'
    
    def verification_badge(self, obj):
        colors = {
            'VERIFIED': 'green',
            'PENDING': 'yellow',
            'REJECTED': 'red',
            'IN_REVIEW': 'blue',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.verification_status, 'gray'),
            obj.get_verification_status_display()
        )
    verification_badge.short_description = 'Verification'


@admin.register(OwnerProfile, site=admin_site)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'total_properties', 'total_revenue', 'created_at')
    search_fields = ('user__email', 'company_name')
    readonly_fields = ('total_properties', 'total_revenue')


@admin.register(TenantProfile, site=admin_site)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employer_name', 'monthly_income', 'is_approved')
    search_fields = ('user__email', 'employer_name')


@admin.register(CaretakerProfile, site=admin_site)
class CaretakerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'owner', 'permission_level', 'is_active')
    list_filter = ('permission_level', 'is_active')
    search_fields = ('user__email', 'owner__user__email')


# ========================================
# PROPERTIES APP REGISTRATIONS
# ========================================

@admin.register(Property, site=admin_site)
class PropertyAdmin(admin.ModelAdmin):
    """Custom Property admin with status badges"""
    list_display = ('title', 'owner_info', 'property_type_badge', 'status_badge', 'verification_badge', 'created_at')
    list_filter = ('property_type', 'availability_status', 'verification_status', 'is_multi_unit')
    search_fields = ('title', 'address', 'city', 'owner__user__email')
    readonly_fields = ('view_count', 'inquiry_count', 'favorite_count')
    
    fieldsets = (
        ('Basic Info', {'fields': ('owner', 'title', 'description', 'property_type')}),
        ('Location', {'fields': ('address', 'city', 'state', 'country', 'postal_code')}),
        ('Pricing', {'fields': ('rental_price', 'service_charge', 'security_deposit')}),
        ('Details', {'fields': ('bedrooms', 'bathrooms', 'parking_spaces', 'square_feet')}),
        ('Multi-Unit', {'fields': ('is_multi_unit', 'total_units', 'available_units')}),
        ('Status', {'fields': ('verification_status', 'availability_status')}),
        ('Media', {'fields': ('main_image', 'thumbnail', 'images')}),
        ('Analytics', {'fields': ('view_count', 'inquiry_count', 'favorite_count')}),
    )
    
    def owner_info(self, obj):
        return format_html(
            '{}<br/><span style="font-size:11px;color:#666;">{}</span>',
            obj.owner.user.get_full_name() if obj.owner else 'N/A',
            obj.owner.user.email if obj.owner else ''
        )
    owner_info.short_description = 'Owner'
    
    def property_type_badge(self, obj):
        colors = {
            'APARTMENT': 'blue',
            'BUNGALOW': 'green',
            'MAISONETTE': 'purple',
            'DUPLEX': 'indigo',
            'PENTHOUSE': 'pink',
            'STUDIO': 'orange',
            'TOWNHOUSE': 'teal',
            'COMMERCIAL': 'red',
            'LAND': 'gray',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.property_type, 'gray'),
            obj.get_property_type_display()
        )
    property_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'AVAILABLE': 'green',
            'RENTED': 'red',
            'UNDER_MAINTENANCE': 'yellow',
            'BOOKED': 'orange',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.availability_status, 'gray'),
            obj.get_availability_status_display()
        )
    status_badge.short_description = 'Status'
    
    def verification_badge(self, obj):
        colors = {
            'VERIFIED': 'green',
            'PENDING': 'yellow',
            'REJECTED': 'red',
            'IN_REVIEW': 'blue',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.verification_status, 'gray'),
            obj.get_verification_status_display()
        )
    verification_badge.short_description = 'Verification'


@admin.register(Unit, site=admin_site)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('unit_number', 'property_obj', 'bedrooms', 'bathrooms', 'status_badge', 'is_available')
    list_filter = ('status', 'is_available')
    search_fields = ('unit_number', 'property_obj__title')
    
    def status_badge(self, obj):
        colors = {
            'AVAILABLE': 'green',
            'RENTED': 'red',
            'BOOKED': 'yellow',
            'UNDER_MAINTENANCE': 'orange',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(PropertyImage, site=admin_site)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_main', 'order', 'uploaded_at')
    list_filter = ('is_main',)


@admin.register(PropertyDocument, site=admin_site)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('property', 'document_type', 'is_verified', 'uploaded_at')
    list_filter = ('document_type', 'is_verified')


# ========================================
# TENANTS APP REGISTRATIONS
# ========================================

@admin.register(TenantApplication, site=admin_site)
class TenantApplicationAdmin(admin.ModelAdmin):
    list_display = ('tenant_info', 'property_info', 'unit_info', 'status_badge', 'created_at')
    list_filter = ('status', 'property__owner')
    search_fields = ('tenant__email', 'tenant__first_name', 'tenant__last_name', 'property__title')
    readonly_fields = ('created_at', 'updated_at')
    
    def tenant_info(self, obj):
        return format_html(
            '{}<br/><span style="font-size:11px;color:#666;">{}</span>',
            obj.tenant.get_full_name(),
            obj.tenant.email
        )
    tenant_info.short_description = 'Tenant'
    
    def property_info(self, obj):
        return format_html(
            '{}<br/><span style="font-size:11px;color:#666;">{}</span>',
            obj.property.title,
            obj.property.city
        )
    property_info.short_description = 'Property'
    
    def unit_info(self, obj):
        if obj.unit:
            return format_html(
                'Unit {}<br/><span style="font-size:11px;color:#666;">{} bed, {} bath</span>',
                obj.unit.unit_number,
                obj.unit.bedrooms,
                obj.unit.bathrooms
            )
        return 'N/A'
    unit_info.short_description = 'Unit'
    
    def status_badge(self, obj):
        colors = {
            'APPROVED': 'green',
            'PENDING': 'yellow',
            'UNDER_REVIEW': 'blue',
            'REJECTED': 'red',
            'CANCELLED': 'gray',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Lease, site=admin_site)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'property', 'unit', 'monthly_rent', 'status_badge', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('tenant__email', 'property__title')
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'gray',
            'PENDING_SIGNATURE': 'yellow',
            'ACTIVE': 'green',
            'EXPIRED': 'orange',
            'TERMINATED': 'red',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# ========================================
# PAYMENTS APP REGISTRATIONS
# ========================================

@admin.register(Payment, site=admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'payer_info', 'amount_display', 'payment_type_badge', 'status_badge', 'created_at')
    list_filter = ('status', 'payment_type', 'payment_method')
    search_fields = ('payment_reference', 'payer__email', 'payer__first_name')
    readonly_fields = ('payment_reference', 'created_at', 'updated_at')
    
    def payer_info(self, obj):
        return format_html(
            '{}<br/><span style="font-size:11px;color:#666;">{}</span>',
            obj.payer.get_full_name(),
            obj.payer.email
        )
    payer_info.short_description = 'Payer'
    
    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:bold;color:#1a56db;">KES {:,}</span>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def payment_type_badge(self, obj):
        colors = {
            'RENT': 'blue',
            'SUBSCRIPTION': 'purple',
            'DEPOSIT': 'green',
            'SERVICE_CHARGE': 'orange',
            'PENALTY': 'red',
            'REFUND': 'gray',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.payment_type, 'gray'),
            obj.get_payment_type_display()
        )
    payment_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'COMPLETED': 'green',
            'PENDING': 'yellow',
            'FAILED': 'red',
            'CANCELLED': 'gray',
            'REFUNDED': 'purple',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Invoice, site=admin_site)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'user', 'amount', 'status', 'due_date')
    list_filter = ('status',)
    search_fields = ('invoice_number', 'user__email')


@admin.register(SubscriptionPlan, site=admin_site)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price_monthly', 'is_active')
    list_filter = ('is_active',)


# ========================================
# MAINTENANCE APP REGISTRATIONS
# ========================================

@admin.register(MaintenanceRequest, site=admin_site)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'property_info', 'tenant_info', 'priority_badge', 'status_badge', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('title', 'tenant__email', 'property__title')
    readonly_fields = ('created_at', 'updated_at')
    
    def property_info(self, obj):
        return format_html(
            '{}<br/><span style="font-size:11px;color:#666;">{}</span>',
            obj.property.title,
            obj.property.city
        )
    property_info.short_description = 'Property'
    
    def tenant_info(self, obj):
        return obj.tenant.get_full_name() if obj.tenant else 'N/A'
    tenant_info.short_description = 'Tenant'
    
    def priority_badge(self, obj):
        colors = {
            'LOW': 'gray',
            'MEDIUM': 'blue',
            'HIGH': 'orange',
            'URGENT': 'red',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'yellow',
            'IN_REVIEW': 'blue',
            'ASSIGNED': 'purple',
            'IN_PROGRESS': 'orange',
            'RESOLVED': 'green',
            'CLOSED': 'gray',
            'CANCELLED': 'red',
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(MaintenanceTask, site=admin_site)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'request', 'assigned_to', 'status', 'due_date')
    list_filter = ('status',)


# ========================================
# COMMUNICATIONS APP REGISTRATIONS
# ========================================

@admin.register(ChatRoom, site=admin_site)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'room_type', 'participant_count', 'created_at')
    filter_horizontal = ('participants',)
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'


@admin.register(Message, site=admin_site)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'room', 'content_preview', 'created_at')
    list_filter = ('message_type',)
    search_fields = ('content', 'sender__email')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Message'


@admin.register(MessageTemplate, site=admin_site)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active')
    list_filter = ('template_type', 'is_active')


# ========================================
# ANALYTICS APP REGISTRATIONS
# ========================================

@admin.register(AnalyticsEvent, site=admin_site)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'property', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('user__email',)
    readonly_fields = ('created_at',)


@admin.register(AnalyticsMetric, site=admin_site)
class AnalyticsMetricAdmin(admin.ModelAdmin):
    list_display = ('metric_type', 'owner', 'property', 'value', 'date')
    list_filter = ('metric_type', 'date')
    search_fields = ('owner__user__email',)


@admin.register(SavedReport, site=admin_site)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'report_type', 'is_scheduled', 'created_at')
    list_filter = ('report_type', 'is_scheduled')


# ========================================
# NOTIFICATIONS APP REGISTRATIONS
# ========================================

@admin.register(Notification, site=admin_site)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('user__email', 'title')
    readonly_fields = ('created_at',)


@admin.register(NotificationPreference, site=admin_site)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__email',)


# ========================================
# SEO APP REGISTRATIONS
# ========================================

@admin.register(SeoMeta, site=admin_site)
class SeoMetaAdmin(admin.ModelAdmin):
    list_display = ('url_path', 'meta_title', 'meta_description')
    search_fields = ('url_path', 'meta_title')
    list_filter = ('created_at',)


@admin.register(SeoRobots, site=admin_site)
class SeoRobotsAdmin(admin.ModelAdmin):
    list_display = ('user_agent', 'is_active', 'created_at')


@admin.register(SeoSitemap, site=admin_site)
class SeoSitemapAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'priority', 'is_active')


@admin.register(SeoRedirect, site=admin_site)
class SeoRedirectAdmin(admin.ModelAdmin):
    list_display = ('old_path', 'new_path', 'redirect_type', 'is_active')
    search_fields = ('old_path', 'new_path')


# ========================================
# LEGAL APP REGISTRATIONS
# ========================================

if LEGAL_MODELS_AVAILABLE:
    @admin.register(TermsOfService, site=admin_site)
    class TermsOfServiceAdmin(admin.ModelAdmin):
        list_display = ('title', 'version', 'is_active', 'created_at')
        list_filter = ('is_active',)
        search_fields = ('title',)

    @admin.register(PrivacyPolicy, site=admin_site)
    class PrivacyPolicyAdmin(admin.ModelAdmin):
        list_display = ('title', 'version', 'is_active', 'created_at')
        list_filter = ('is_active',)
        search_fields = ('title',)


# ========================================
# REGISTER DJANGO'S DEFAULT GROUP MODEL
# ========================================

admin_site.register(Group, GroupAdmin)