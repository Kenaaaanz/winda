from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class PageView(models.Model):
    """Track page views"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    referer = models.URLField(blank=True, null=True)
    query_params = models.JSONField(default=dict, blank=True)
    response_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_page_views'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['path', 'created_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"{self.path} - {self.created_at}"


class UserActivity(models.Model):
    """Track user actions"""
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
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_activity_type_display()}"


class DailyAnalyticsReport(models.Model):
    """Daily analytics report"""
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