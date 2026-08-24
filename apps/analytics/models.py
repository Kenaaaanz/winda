from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class DashboardMetric(models.Model):
    """Stored dashboard metrics for performance"""
    METRIC_TYPES = (
        ('OWNER', 'Owner Metrics'),
        ('TENANT', 'Tenant Metrics'),
        ('PLATFORM', 'Platform Metrics'),
        ('PROPERTY', 'Property Metrics'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_metrics', null=True, blank=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    
    # Metrics data
    data = models.JSONField(default=dict)
    
    # Date range
    date_from = models.DateField()
    date_to = models.DateField()
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_dashboard_metrics'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['user', 'metric_type']),
            models.Index(fields=['generated_at']),
        ]
    
    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.user.get_full_name() if self.user else 'Platform'}"


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


class AnalyticsReport(models.Model):
    """Pre-generated analytics reports"""
    REPORT_TYPES = (
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('QUARTERLY', 'Quarterly Report'),
        ('YEARLY', 'Yearly Report'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_reports', null=True, blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Report data
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    data = models.JSONField(default=dict)
    
    # Date range
    date_from = models.DateField()
    date_to = models.DateField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_reports'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_report_type_display()}"