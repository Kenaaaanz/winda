from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class AnalyticsMetric(models.Model):
    """Store analytics metrics for reporting"""
    METRIC_TYPES = (
        ('REVENUE', 'Revenue'),
        ('APPLICATIONS', 'Applications'),
        ('TENANTS', 'Tenants'),
        ('MAINTENANCE', 'Maintenance'),
        ('PROPERTY_VIEWS', 'Property Views'),
        ('UNIT_OCCUPANCY', 'Unit Occupancy'),
        ('PLATFORM_FEES', 'Platform Fees'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('accounts.OwnerProfile', on_delete=models.CASCADE, related_name='analytics_metrics', null=True, blank=True)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='analytics_metrics', null=True, blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    count = models.PositiveIntegerField(default=0)
    date = models.DateField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_metrics'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['owner', 'metric_type', 'date']),
            models.Index(fields=['property', 'metric_type', 'date']),
        ]
    
    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.date}"


class AnalyticsEvent(models.Model):
    """Track user events for analytics"""
    EVENT_TYPES = (
        ('PAGE_VIEW', 'Page View'),
        ('PROPERTY_VIEW', 'Property View'),
        ('APPLICATION_SUBMIT', 'Application Submit'),
        ('APPLICATION_APPROVE', 'Application Approve'),
        ('APPLICATION_REJECT', 'Application Reject'),
        ('PAYMENT_INITIATE', 'Payment Initiate'),
        ('PAYMENT_COMPLETE', 'Payment Complete'),
        ('PAYMENT_FAIL', 'Payment Fail'),
        ('LEASE_SIGN', 'Lease Sign'),
        ('LEASE_TERMINATE', 'Lease Terminate'),
        ('MAINTENANCE_REQUEST', 'Maintenance Request'),
        ('MAINTENANCE_RESOLVE', 'Maintenance Resolve'),
        ('MESSAGE_SENT', 'Message Sent'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
        ('USER_REGISTER', 'User Register'),
        ('PROPERTY_LIST', 'Property List'),
        ('UNIT_CREATE', 'Unit Create'),
        ('SEARCH', 'Search'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_events', null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    
    # Related objects
    property = models.ForeignKey('properties.Property', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Event data
    data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referer = models.URLField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['property', 'event_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.user.get_full_name() if self.user else 'Anonymous'}"


class SavedReport(models.Model):
    """Saved custom reports for owners"""
    REPORT_TYPES = (
        ('TENANT', 'Tenant Report'),
        ('PROPERTY', 'Property Report'),
        ('PAYMENT', 'Payment Report'),
        ('MAINTENANCE', 'Maintenance Report'),
        ('CUSTOM', 'Custom Report'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('accounts.OwnerProfile', on_delete=models.CASCADE, related_name='saved_reports')
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Report configuration
    date_from = models.DateField()
    date_to = models.DateField()
    metrics = models.JSONField(default=list)  # List of metrics to include
    filters = models.JSONField(default=dict, blank=True)  # Additional filters
    chart_type = models.CharField(max_length=20, default='line')
    
    # Schedule (for recurring reports)
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=20, choices=[
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ], null=True, blank=True)
    last_generated = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'saved_reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_report_type_display()}"


class ReportExport(models.Model):
    """Track exported reports"""
    EXPORT_FORMATS = (
        ('CSV', 'CSV'),
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('accounts.OwnerProfile', on_delete=models.CASCADE, related_name='report_exports')
    saved_report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name='exports', null=True, blank=True)
    title = models.CharField(max_length=200)
    format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    file = models.FileField(upload_to='reports/exports/', null=True, blank=True)
    data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'report_exports'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.title} - {self.generated_at}"


class DailyAnalyticsReport(models.Model):
    """Daily aggregated analytics report"""
    date = models.DateField(unique=True)
    
    # General statistics
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    
    # Property statistics
    total_properties = models.PositiveIntegerField(default=0)
    new_properties = models.PositiveIntegerField(default=0)
    properties_views = models.PositiveIntegerField(default=0)
    
    # Transaction statistics
    total_payments = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    new_applications = models.PositiveIntegerField(default=0)
    
    # Engagement
    messages_sent = models.PositiveIntegerField(default=0)
    maintenance_requests = models.PositiveIntegerField(default=0)
    chat_rooms_created = models.PositiveIntegerField(default=0)
    
    # Revenue
    platform_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subscription_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Data
    data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_daily_reports'
        ordering = ['-date']
    
    def __str__(self):
        return f"Report for {self.date}"