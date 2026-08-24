from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

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
    )
    
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