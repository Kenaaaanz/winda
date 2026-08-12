from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
from decimal import Decimal

User = get_user_model()

class Payment(models.Model):
    PAYMENT_TYPES = (
        ('RENT', 'Rent'),
        ('SUBSCRIPTION', 'Subscription'),
        ('DEPOSIT', 'Security Deposit'),
        ('SERVICE_CHARGE', 'Service Charge'),
        ('PENALTY', 'Penalty'),
        ('REFUND', 'Refund'),
    )
    
    PAYMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    )
    
    PAYMENT_METHODS = (
        ('PAYSTACK', 'Paystack'),
        ('MPESA', 'M-Pesa'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CARD', 'Card'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    payer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments_made')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments_received', null=True, blank=True)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    lease = models.ForeignKey('tenants.Lease', on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Payment Details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    description = models.TextField(blank=True)
    
    # Platform Fee Breakdown (3% to Winda, 97% to Owner)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # 3% of amount
    owner_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # 97% of amount
    
    # Payment Method
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='PAYSTACK')
    payment_reference = models.CharField(max_length=100, unique=True)
    paystack_subaccount_code = models.CharField(max_length=100, blank=True, help_text='Paystack subaccount code')
    payment_link = models.URLField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    
    # Timestamps
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payer', 'status']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['payment_reference']),
            models.Index(fields=['due_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} {self.currency}"
    
    def calculate_fee_split(self, platform_fee_percent=Decimal('3.00')):
        """Calculate the 3% platform fee and 97% owner amount"""
        self.platform_fee = (self.amount * platform_fee_percent / 100).quantize(Decimal('0.01'))
        self.owner_amount = (self.amount - self.platform_fee).quantize(Decimal('0.01'))
        return {
            'platform_fee': self.platform_fee,
            'owner_amount': self.owner_amount,
            'platform_percentage': platform_fee_percent,
        }
    
    def mark_as_completed(self, reference=None):
        self.status = 'COMPLETED'
        self.paid_at = timezone.now()
        if reference:
            self.payment_reference = reference
        self.save()
    
    def mark_as_failed(self, reason=None):
        self.status = 'FAILED'
        if reason:
            self.failure_reason = reason
        self.save()
    
    def refund(self):
        self.status = 'REFUNDED'
        self.save()


class SubscriptionPlan(models.Model):
    PLAN_TYPES = (
        ('BASIC', 'Basic'),
        ('PREMIUM', 'Premium'),
        ('ENTERPRISE', 'Enterprise'),
    )

    name = models.CharField(max_length=50)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    description = models.TextField(blank=True)

    # Pricing
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    monthly_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Features
    max_properties = models.PositiveIntegerField(default=5)
    max_tenants = models.PositiveIntegerField(default=20)
    featured_listings = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)

    # Limits
    property_limit = models.PositiveIntegerField(default=5)
    tenant_limit = models.PositiveIntegerField(default=20)
    storage_limit_gb = models.PositiveIntegerField(default=5)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscription_plans'

    def __str__(self):
        return f"{self.name} - {self.price_monthly}/month"

    def get_charge_for_period(self, period='monthly'):
        if period == 'yearly':
            return self.price_yearly
        return self.price_monthly


class Invoice(models.Model):
    INVOICE_STATUS = (
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True)
    
    # Relationships
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='invoice')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    
    # Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    issue_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='DRAFT')
    
    # Files
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    
    class Meta:
        db_table = 'invoices'
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.user.get_full_name()}"
    
    def generate_pdf(self):
        # Generate PDF using reportlab or similar
        pass