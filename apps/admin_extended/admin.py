from django.contrib.admin import AdminSite
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Import all models from all apps
from apps.accounts.models import User, OwnerProfile, TenantProfile, CaretakerProfile
from apps.properties.models import Property, Unit, PropertyImage, PropertyDocument
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment, Invoice, SubscriptionPlan
from apps.maintenance.models import MaintenanceRequest, MaintenanceTask
from apps.communications.models import ChatRoom, Message, MessageTemplate
from apps.analytics.models import AnalyticsEvent, AnalyticsMetric, SavedReport
from apps.notifications.models import Notification, NotificationPreference
from apps.seo.models import SeoMeta, SeoRobots, SeoSitemap, SeoRedirect


User = get_user_model()


class WindaAdminSite(AdminSite):
    """
    Custom admin site that preserves ALL Django admin functionality.
    Only the dashboard index page is customized with stats cards.
    """
    
    site_header = 'Winda Super Admin'
    site_title = 'Winda Admin'
    index_title = 'Platform Dashboard'
    site_url = '/'
    
    # CRITICAL: Use custom base template for ALL admin pages
    base_template = 'admin/superadmin_base.html'
    
    def each_context(self, request):
        """Add context data to ALL admin pages for the sidebar."""
        context = super().each_context(request)
        
        # Only add sidebar data for superusers
        if request.user.is_superuser:
            today = timezone.now().date()
            
            # Get data for right sidebar
            total_users = User.objects.filter(is_active=True).count()
            total_properties = Property.objects.count()
            active_leases = Lease.objects.filter(status='ACTIVE').count()
            pending_maintenance = MaintenanceRequest.objects.filter(
                status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
            ).count()
            
            # Messages today
            messages_today = Message.objects.filter(
                created_at__date=today,
                is_deleted=False
            ).count()
            
            # New applications today
            new_applications = TenantApplication.objects.filter(
                created_at__date=today
            ).count()
            
            # Payments today
            payments_today = Payment.objects.filter(
                status='COMPLETED',
                paid_at__date=today
            ).count()
            
            # Revenue chart data (last 30 days)
            revenue_labels = []
            revenue_data = []
            for i in range(30, -1, -1):
                date = today - timedelta(days=i)
                revenue_labels.append(date.strftime('%b %d'))
                revenue = Payment.objects.filter(
                    status='COMPLETED',
                    paid_at__date=date
                ).aggregate(total=Sum('amount'))['total'] or 0
                revenue_data.append(float(revenue))
            
            # User chart data (last 30 days)
            user_labels = []
            user_data = []
            for i in range(30, -1, -1):
                date = today - timedelta(days=i)
                user_labels.append(date.strftime('%b %d'))
                count = User.objects.filter(date_joined__date=date).count()
                user_data.append(count)
            
            context.update({
                'total_users': total_users,
                'total_properties': total_properties,
                'active_leases': active_leases,
                'pending_maintenance': pending_maintenance,
                'pending_maintenance_count': pending_maintenance,
                'messages_today': messages_today,
                'new_applications': new_applications,
                'payments_today': payments_today,
                'revenue_labels': revenue_labels,
                'revenue_data': revenue_data,
                'user_labels': user_labels,
                'user_data': user_data,
            })
        
        return context
    
    def index(self, request, extra_context=None):
        """Custom dashboard with stats cards."""
        if not request.user.is_superuser:
            return super().index(request, extra_context)
        
        context = {
            'app_list': self.get_app_list(request),
            'title': self.index_title,
            'subtitle': 'Platform Overview & Analytics',
        }
        
        context['stats'] = self.get_platform_stats()
        context['recent_activities'] = self.get_recent_activities()
        context['quick_actions'] = self.get_quick_actions()
        
        if extra_context:
            context.update(extra_context)
        
        return super().index(request, context)
    
    def get_platform_stats(self):
        """Get platform-wide statistics for superadmin dashboard."""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)
        
        # ========================================
        # USER STATS
        # ========================================
        total_users = User.objects.filter(is_active=True).count()
        new_users_week = User.objects.filter(date_joined__date__gte=last_week).count()
        new_users_month = User.objects.filter(date_joined__date__gte=last_month).count()
        
        owners = User.objects.filter(user_type='HOUSE_OWNER', is_active=True).count()
        tenants = User.objects.filter(user_type='TENANT', is_active=True).count()
        caretakers = User.objects.filter(user_type='CARETAKER', is_active=True).count()
        pending_verifications = User.objects.filter(
            user_type='HOUSE_OWNER',
            verification_status='PENDING'
        ).count()
        
        # ========================================
        # PROPERTY STATS
        # ========================================
        total_properties = Property.objects.count()
        pending_properties = Property.objects.filter(verification_status='PENDING').count()
        verified_properties = Property.objects.filter(verification_status='VERIFIED').count()
        rejected_properties = Property.objects.filter(verification_status='REJECTED').count()
        
        multi_unit_buildings = Property.objects.filter(is_multi_unit=True).count()
        
        total_units = Unit.objects.count()
        available_units = Unit.objects.filter(is_available=True).count()
        rented_units = Unit.objects.filter(status='RENTED').count()
        booked_units = Unit.objects.filter(status='BOOKED').count()
        under_maintenance_units = Unit.objects.filter(status='UNDER_MAINTENANCE').count()
        
        # ========================================
        # APPLICATION STATS
        # ========================================
        total_applications = TenantApplication.objects.count()
        pending_applications = TenantApplication.objects.filter(status='PENDING').count()
        under_review_applications = TenantApplication.objects.filter(status='UNDER_REVIEW').count()
        approved_applications = TenantApplication.objects.filter(status='APPROVED').count()
        rejected_applications = TenantApplication.objects.filter(status='REJECTED').count()
        applications_this_month = TenantApplication.objects.filter(
            created_at__date__gte=last_month
        ).count()
        
        # ========================================
        # PAYMENT STATS
        # ========================================
        completed_payments = Payment.objects.filter(status='COMPLETED')
        total_revenue = completed_payments.aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        weekly_revenue = Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=last_week
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        platform_fees = total_revenue * Decimal('0.03')
        pending_payments = Payment.objects.filter(status='PENDING').count()
        failed_payments = Payment.objects.filter(status='FAILED').count()
        
        # ========================================
        # MAINTENANCE STATS
        # ========================================
        total_maintenance = MaintenanceRequest.objects.count()
        pending_maintenance = MaintenanceRequest.objects.filter(
            status__in=['PENDING', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS']
        ).count()
        resolved_maintenance = MaintenanceRequest.objects.filter(status='RESOLVED').count()
        
        # ========================================
        # LEASE STATS
        # ========================================
        total_leases = Lease.objects.count()
        active_leases = Lease.objects.filter(status='ACTIVE').count()
        pending_signature = Lease.objects.filter(status='PENDING_SIGNATURE').count()
        expiring_soon = Lease.objects.filter(
            status='ACTIVE',
            end_date__lte=today + timedelta(days=30)
        ).count()
        
        # ========================================
        # COMMUNICATION STATS
        # ========================================
        total_chat_rooms = ChatRoom.objects.filter(is_active=True).count()
        total_messages = Message.objects.filter(is_deleted=False).count()
        messages_this_week = Message.objects.filter(
            created_at__date__gte=last_week,
            is_deleted=False
        ).count()
        
        return {
            'users': {
                'total': total_users,
                'new_week': new_users_week,
                'new_month': new_users_month,
                'owners': owners,
                'tenants': tenants,
                'caretakers': caretakers,
                'pending_verifications': pending_verifications,
            },
            'properties': {
                'total': total_properties,
                'pending': pending_properties,
                'verified': verified_properties,
                'rejected': rejected_properties,
                'multi_unit': multi_unit_buildings,
                'total_units': total_units,
                'available_units': available_units,
                'rented_units': rented_units,
                'booked_units': booked_units,
                'under_maintenance': under_maintenance_units,
            },
            'applications': {
                'total': total_applications,
                'pending': pending_applications,
                'under_review': under_review_applications,
                'approved': approved_applications,
                'rejected': rejected_applications,
                'this_month': applications_this_month,
            },
            'payments': {
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'weekly_revenue': float(weekly_revenue),
                'platform_fees': float(platform_fees),
                'pending': pending_payments,
                'failed': failed_payments,
            },
            'maintenance': {
                'total': total_maintenance,
                'pending': pending_maintenance,
                'resolved': resolved_maintenance,
            },
            'leases': {
                'total': total_leases,
                'active': active_leases,
                'pending_signature': pending_signature,
                'expiring_soon': expiring_soon,
            },
            'communications': {
                'chat_rooms': total_chat_rooms,
                'messages': total_messages,
                'messages_this_week': messages_this_week,
            },
            'growth': {
                'new_users': new_users_month,
                'new_properties': Property.objects.filter(created_at__date__gte=last_month).count(),
                'new_applications': applications_this_month,
            }
        }
    
    def get_recent_activities(self):
        """Get recent platform activities for superadmin dashboard."""
        activities = []
        
        recent_users = User.objects.order_by('-date_joined')[:3]
        for user in recent_users:
            activities.append({
                'type': 'New User',
                'icon': 'user-plus',
                'color': 'blue',
                'description': f'{user.get_full_name()} registered as {user.get_user_type_display()}',
                'time': user.date_joined,
                'time_ago': self.get_time_ago(user.date_joined),
            })
        
        recent_properties = Property.objects.order_by('-created_at')[:3]
        for prop in recent_properties:
            status = 'verified' if prop.verification_status == 'VERIFIED' else 'listed'
            activities.append({
                'type': 'Property',
                'icon': 'home',
                'color': 'green',
                'description': f'Property "{prop.title}" {status} by {prop.owner.user.get_full_name()}',
                'time': prop.created_at,
                'time_ago': self.get_time_ago(prop.created_at),
            })
        
        recent_payments = Payment.objects.filter(status='COMPLETED').order_by('-paid_at')[:3]
        for payment in recent_payments:
            activities.append({
                'type': 'Payment',
                'icon': 'money-bill-wave',
                'color': 'yellow',
                'description': f'Payment of KES {payment.amount:,.2f} from {payment.payer.get_full_name()}',
                'time': payment.paid_at,
                'time_ago': self.get_time_ago(payment.paid_at),
            })
        
        recent_apps = TenantApplication.objects.order_by('-created_at')[:3]
        for app in recent_apps:
            activities.append({
                'type': 'Application',
                'icon': 'file-signature',
                'color': 'purple',
                'description': f'{app.tenant.get_full_name()} applied for {app.property.title}',
                'time': app.created_at,
                'time_ago': self.get_time_ago(app.created_at),
            })
        
        recent_maintenance = MaintenanceRequest.objects.order_by('-created_at')[:3]
        for req in recent_maintenance:
            activities.append({
                'type': 'Maintenance',
                'icon': 'tools',
                'color': 'red',
                'description': f'{req.tenant.get_full_name()} reported: {req.title}',
                'time': req.created_at,
                'time_ago': self.get_time_ago(req.created_at),
            })
        
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
    def get_quick_actions(self):
        """Get quick actions for superadmin."""
        return [
            {'name': 'All Users', 'url': '/admin/accounts/user/', 'icon': 'fa-users-cog', 'color': 'blue'},
            {'name': 'Verify Properties', 'url': '/admin/properties/property/?verification_status__exact=PENDING', 'icon': 'fa-check-circle', 'color': 'yellow'},
            {'name': 'All Properties', 'url': '/admin/properties/property/', 'icon': 'fa-home', 'color': 'green'},
            {'name': 'All Payments', 'url': '/admin/payments/payment/', 'icon': 'fa-credit-card', 'color': 'purple'},
            {'name': 'Maintenance', 'url': '/admin/maintenance/maintenancerequest/', 'icon': 'fa-tools', 'color': 'red'},
            {'name': 'SEO Settings', 'url': '/admin/seo/seometa/', 'icon': 'fa-search', 'color': 'indigo'},
            {'name': 'Analytics', 'url': '/admin/analytics/', 'icon': 'fa-chart-line', 'color': 'pink'},
            {'name': 'Notifications', 'url': '/admin/notifications/', 'icon': 'fa-bell', 'color': 'orange'},
            {'name': 'Communications', 'url': '/admin/communications/', 'icon': 'fa-comment-dots', 'color': 'green'},
        ]
    
    def get_time_ago(self, time):
        """Get time ago string."""
        if not time:
            return ''
        diff = timezone.now() - time
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes}m ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours}h ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days}d ago'
        else:
            return time.strftime('%b %d, %Y')


# ========================================
# REGISTER ALL MODELS WITH CUSTOM ADMIN SITE
# ========================================

# Create admin site instance
admin_site = WindaAdminSite(name='admin')


# ========================================
# ACCOUNTS APP
# ========================================

@admin.register(User, site=admin_site)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'verification_status', 'is_active', 'date_joined')
    list_filter = ('user_type', 'verification_status', 'is_active')
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
# PROPERTIES APP
# ========================================

@admin.register(Property, site=admin_site)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'city', 'rental_price', 'verification_status', 'availability_status', 'created_at')
    list_filter = ('verification_status', 'availability_status', 'property_type', 'is_multi_unit')
    search_fields = ('title', 'address', 'city', 'owner__user__email')
    readonly_fields = ('view_count', 'inquiry_count', 'favorite_count')


@admin.register(Unit, site=admin_site)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('unit_number', 'property_obj', 'bedrooms', 'bathrooms', 'status', 'is_available')
    list_filter = ('status', 'is_available')
    search_fields = ('unit_number', 'property_obj__title')


@admin.register(PropertyImage, site=admin_site)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_main', 'order', 'uploaded_at')
    list_filter = ('is_main',)


@admin.register(PropertyDocument, site=admin_site)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('property', 'document_type', 'is_verified', 'uploaded_at')
    list_filter = ('document_type', 'is_verified')


# ========================================
# TENANTS APP
# ========================================

@admin.register(TenantApplication, site=admin_site)
class TenantApplicationAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'property', 'unit', 'status', 'created_at')
    list_filter = ('status', 'property__owner')
    search_fields = ('tenant__email', 'property__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Lease, site=admin_site)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'property', 'unit', 'monthly_rent', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('tenant__email', 'property__title')


# ========================================
# PAYMENTS APP
# ========================================

@admin.register(Payment, site=admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'payer', 'amount', 'payment_type', 'status', 'created_at')
    list_filter = ('status', 'payment_type', 'payment_method')
    search_fields = ('payment_reference', 'payer__email')
    readonly_fields = ('payment_reference', 'created_at')


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
# MAINTENANCE APP
# ========================================

@admin.register(MaintenanceRequest, site=admin_site)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'property', 'tenant', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('title', 'tenant__email', 'property__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MaintenanceTask, site=admin_site)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'request', 'assigned_to', 'status', 'due_date')
    list_filter = ('status',)


# ========================================
# COMMUNICATIONS APP
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
# ANALYTICS APP
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
# NOTIFICATIONS APP
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
# SEO APP
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


# Register Group (Django's built-in)
admin_site.register(Group, GroupAdmin)


# Print confirmation when admin loads
print("✅ Custom Winda Admin Site loaded successfully!")
print(f"✅ Site header: {admin_site.site_header}")
print(f"✅ Base template: {admin_site.base_template}")