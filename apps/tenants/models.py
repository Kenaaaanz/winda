from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid

User = get_user_model()

class TenantApplication(models.Model):
    APPLICATION_STATUS = (
        ('PENDING', 'Pending'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='applications')
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    
    # Application Details
    intended_move_in_date = models.DateField()
    preferred_lease_duration = models.PositiveIntegerField(help_text='Duration in months')
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2)
    employment_status = models.CharField(max_length=50)
    
    # Documents
    application_documents = models.JSONField(default=list, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='PENDING')
    owner_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    
    class Meta:
        db_table = 'tenant_applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['unit', 'status']),
        ]
    
    def __str__(self):
        return f"{self.tenant.get_full_name()} - {self.property.title}" + (f" - Unit {self.unit.unit_number}" if self.unit else "")

class Lease(models.Model):
    LEASE_STATUS = (
        ('DRAFT', 'Draft'),
        ('PENDING_SIGNATURE', 'Pending Signature'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('TERMINATED', 'Terminated'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leases')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='leases')
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True, related_name='leases')
    
    # Lease Details
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Terms
    termination_notice_period = models.PositiveIntegerField(default=30, help_text='Termination notice period in days')
    late_payment_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Documents
    lease_agreement = models.FileField(upload_to='leases/', null=True, blank=True)
    signed_lease = models.FileField(upload_to='leases/signed/', null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=LEASE_STATUS, default='DRAFT')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leases'
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"Lease: {self.tenant.get_full_name()} - {self.property.title}"
    
    def is_active(self):
        """Check if lease is currently active"""
        today = timezone.now().date()
        return self.status == 'ACTIVE' and self.start_date <= today <= self.end_date
    
    def get_days_remaining(self):
        """Get days remaining in lease"""
        if self.status == 'ACTIVE':
            today = timezone.now().date()
            return (self.end_date - today).days
        return 0


class LeaseAgreementTemplate(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField()
    variables = models.JSONField(default=list, help_text='List of variables that can be replaced')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lease_templates'
    
    def __str__(self):
        return self.name


class LeaseRenewal(models.Model):
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='renewals')
    new_start_date = models.DateField()
    new_end_date = models.DateField()
    new_monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=(
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ), default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'lease_renewals'
    
    def __str__(self):
        return f"Renewal for {self.lease}"