from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class UserActivity(models.Model):
    """Track user activities across the platform"""
    ACTIVITY_TYPES = (
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'View'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('PAYMENT', 'Payment'),
        ('MESSAGE', 'Message'),
        ('APPLICATION', 'Application'),
        ('MAINTENANCE', 'Maintenance'),
    )
    
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=50, blank=True)
    data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_user_activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['related_object_type', 'related_object_id']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_activity_type_display()}"


class AnalyticsReport(models.Model):
    """Saved analytics reports"""
    REPORT_TYPES = (
        ('PROPERTY', 'Property Report'),
        ('TENANT', 'Tenant Report'),
        ('FINANCIAL', 'Financial Report'),
        ('MAINTENANCE', 'Maintenance Report'),
        ('CUSTOM', 'Custom Report'),
    )
    
    FORMATS = (
        ('PDF', 'PDF'),
        ('CSV', 'CSV'),
        ('EXCEL', 'Excel'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    format = models.CharField(max_length=10, choices=FORMATS, default='PDF')
    filters = models.JSONField(default=dict, blank=True)
    data = models.JSONField(default=dict, blank=True)
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=20, blank=True, choices=[
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ])
    last_generated = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"


class AnalyticsDashboard(models.Model):
    """Custom dashboard configuration"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='analytics_dashboard')
    widgets = models.JSONField(default=list, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_dashboards'
    
    def __str__(self):
        return f"Dashboard for {self.user.get_full_name()}"


class AnalyticsMetric(models.Model):
    """Tracked metrics for trends"""
    METRIC_TYPES = (
        ('PROPERTY_VIEWS', 'Property Views'),
        ('APPLICATIONS', 'Applications'),
        ('PAYMENTS', 'Payments'),
        ('MAINTENANCE', 'Maintenance'),
        ('TENANTS', 'Tenants'),
        ('REVENUE', 'Revenue'),
        ('PLATFORM_FEES', 'Platform Fees'),
        ('USER_ENGAGEMENT', 'User Engagement'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey('accounts.OwnerProfile', on_delete=models.CASCADE, null=True, blank=True)
    value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    count = models.PositiveIntegerField(default=0)
    date = models.DateField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_metrics'
        indexes = [
            models.Index(fields=['metric_type', 'date']),
            models.Index(fields=['owner', 'metric_type']),
            models.Index(fields=['property', 'metric_type']),
        ]
    
    def __str__(self):
        return f"{self.metric_type} - {self.date}"


class DailyAnalyticsReport(models.Model):
    """Daily analytics report for quick reference"""
    date = models.DateField(unique=True)
    
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    
    total_properties = models.PositiveIntegerField(default=0)
    new_properties = models.PositiveIntegerField(default=0)
    properties_views = models.PositiveIntegerField(default=0)
    
    total_payments = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    new_applications = models.PositiveIntegerField(default=0)
    
    messages_sent = models.PositiveIntegerField(default=0)
    maintenance_requests = models.PositiveIntegerField(default=0)
    chat_rooms_created = models.PositiveIntegerField(default=0)
    
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_daily_reports'
        ordering = ['-date']
    
    def __str__(self):
        return f"Report for {self.date}"