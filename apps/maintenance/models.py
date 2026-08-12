from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class MaintenanceRequest(models.Model):
    PRIORITY_LEVELS = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_REVIEW', 'In Review'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    CATEGORIES = (
        ('PLUMBING', 'Plumbing'),
        ('ELECTRICAL', 'Electrical'),
        ('STRUCTURAL', 'Structural'),
        ('APPLIANCE', 'Appliance'),
        ('FURNITURE', 'Furniture'),
        ('PEST_CONTROL', 'Pest Control'),
        ('CLEANING', 'Cleaning'),
        ('LANDSCAPING', 'Landscaping'),
        ('OTHER', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='maintenance_requests')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='maintenance_requests')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_maintenance')
    
    # Details
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='MEDIUM')
    
    # Media
    images = models.JSONField(default=list, blank=True)
    videos = models.JSONField(default=list, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    resolution_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Scheduling
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time_start = models.TimeField(null=True, blank=True)
    preferred_time_end = models.TimeField(null=True, blank=True)
    
    # Estimated cost
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        db_table = 'maintenance_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def assign(self, user):
        self.assigned_to = user
        self.assigned_at = timezone.now()
        self.status = 'ASSIGNED'
        self.save()
    
    def resolve(self, notes=None):
        self.status = 'RESOLVED'
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
    
    def close(self):
        self.status = 'CLOSED'
        self.closed_at = timezone.now()
        self.save()
    
    def get_time_in_progress(self):
        if self.assigned_at and self.resolved_at:
            return self.resolved_at - self.assigned_at
        return None


class MaintenanceTask(models.Model):
    TASK_STATUS = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'maintenance_tasks'
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def complete(self):
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()


class MaintenanceChecklist(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    items = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'maintenance_checklists'
    
    def __str__(self):
        return self.name