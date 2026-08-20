from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from phone_field import PhoneField
import uuid


class User(AbstractUser):
    USER_TYPES = (
        ('SUPER_ADMIN', 'Super Admin'),
        ('HOUSE_OWNER', 'House Owner'),
        ('CARETAKER', 'Caretaker'),
        ('TENANT', 'Tenant'),
        ('GUEST', 'Guest'),
    )
    
    VERIFICATION_STATUS = (
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('IN_REVIEW', 'In Review'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='GUEST')
    phone = PhoneField(blank=True, help_text='Contact phone number')
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    # Verification
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    verification_documents = models.JSONField(default=list, blank=True)
    
    # Timestamps
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Preferences
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    notification_preferences = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email', 'user_type']),
            models.Index(fields=['verification_status']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def profile_picture_url(self):
        """Get optimized profile picture URL"""
        if self.profile_picture:
            from apps.common.utils.cloudinary_utils import CloudinaryService
            try:
                public_id = self.profile_picture.name
                return CloudinaryService.get_thumbnail_url(public_id, width=200, height=200, crop='fill')
            except:
                return self.profile_picture.url if self.profile_picture else None
        return None
    
    @property
    def is_verified(self):
        return self.verification_status == 'VERIFIED'
    
    @property
    def is_owner(self):
        return self.user_type == 'HOUSE_OWNER'
    
    @property
    def is_tenant(self):
        return self.user_type == 'TENANT'
    
    @property
    def is_caretaker(self):
        return self.user_type == 'CARETAKER'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Business/Organization Details (for Owners)
    business_name = models.CharField(max_length=200, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = PhoneField(blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    # Preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[('EMAIL', 'Email'), ('PHONE', 'Phone'), ('SMS', 'SMS')],
        default='EMAIL'
    )
    marketing_opt_in = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"Profile for {self.user.get_full_name()}"


class OwnerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='owner_profile')
    company_name = models.CharField(max_length=200)
    company_registration_number = models.CharField(max_length=50, blank=True)
    tax_pin = models.CharField(max_length=50, blank=True)
    business_license = models.FileField(upload_to='documents/business_licenses/', null=True, blank=True)
    
    # Bank Account Info
    bank_account_set_up = models.BooleanField(default=False)
    paystack_subaccount_verified = models.BooleanField(default=False)
    
    # Statistics
    total_properties = models.IntegerField(default=0)
    total_tenants = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fees_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'owner_profiles'
    
    def __str__(self):
        return f"Owner: {self.company_name}"
    
    def has_active_subaccount(self):
        """Check if owner has an active Paystack subaccount"""
        return hasattr(self, 'paystack_subaccount') and self.paystack_subaccount.is_active


class PaystackSubaccount(models.Model):
    owner_profile = models.OneToOneField(OwnerProfile, on_delete=models.CASCADE, related_name='paystack_subaccount')
    
    # Bank Details
    bank_code = models.CharField(max_length=10, help_text='Paystack bank code')
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=200)
    
    # Paystack Subaccount Info
    subaccount_code = models.CharField(max_length=100, unique=True)
    business_name = models.CharField(max_length=200)
    percentage_charge = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'), help_text='Percentage charge for Winda (owner gets 97%)')
    
    # Status
    is_active = models.BooleanField(default=True)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('VERIFIED', 'Verified'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    
    # Metadata
    paystack_response = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paystack_subaccounts'
    
    def __str__(self):
        return f"Subaccount: {self.account_name} ({self.subaccount_code})"

    @property
    def bank_name(self):
        """The settlement-bank name confirmed by Paystack, with a safe fallback."""
        return (
            self.paystack_response.get('settlement_bank')
            or self.paystack_response.get('bank_name')
            or self.bank_code
        )


class TenantProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_profile')
    
    # Employment Details
    employer_name = models.CharField(max_length=200, blank=True)
    employer_contact = PhoneField(blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Guarantor Information
    guarantor_name = models.CharField(max_length=200, blank=True)
    guarantor_phone = PhoneField(blank=True)
    guarantor_email = models.EmailField(blank=True)
    guarantor_relationship = models.CharField(max_length=50, blank=True)
    
    # Rental History
    previous_rental_address = models.TextField(blank=True)
    previous_landlord_name = models.CharField(max_length=200, blank=True)
    previous_landlord_phone = PhoneField(blank=True)
    previous_rental_duration = models.CharField(max_length=50, blank=True)
    
    # Documents
    national_id = models.FileField(upload_to='documents/ids/', null=True, blank=True)
    passport_photo = models.ImageField(upload_to='documents/passports/', null=True, blank=True)
    employment_letter = models.FileField(upload_to='documents/employment/', null=True, blank=True)
    bank_statement = models.FileField(upload_to='documents/bank/', null=True, blank=True)
    
    # References
    reference_name = models.CharField(max_length=200, blank=True)
    reference_phone = PhoneField(blank=True)
    reference_email = models.EmailField(blank=True)
    
    # Tenant Status
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tenant_profiles'
    
    def __str__(self):
        return f"Tenant: {self.user.get_full_name()}"


class CaretakerProfile(models.Model):
    """Caretaker profile - SINGLE DEFINITION"""
    PERMISSION_LEVELS = (
        ('BASIC', 'Basic - View Only'),
        ('STANDARD', 'Standard - View & Respond'),
        ('FULL', 'Full - Manage Properties'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='caretaker_profile')
    owner = models.ForeignKey(OwnerProfile, on_delete=models.CASCADE, related_name='caretakers', null=True, blank=True)
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVELS, default='BASIC')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'caretaker_profiles'
        verbose_name = 'Caretaker Profile'
        verbose_name_plural = 'Caretaker Profiles'
    
    def __str__(self):
        return f"Caretaker: {self.user.get_full_name()}"
    
    def get_assigned_property_ids(self):
        """Get list of assigned property IDs"""
        return list(CaretakerPropertyAssignment.objects.filter(
            caretaker=self,
            is_active=True
        ).values_list('property_id', flat=True))
    
    def has_access_to_property(self, property_id):
        """Check if caretaker has access to a specific property"""
        if self.permission_level == 'FULL':
            return True
        return CaretakerPropertyAssignment.objects.filter(
            caretaker=self,
            property_id=property_id,
            is_active=True
        ).exists()
    
    def get_assigned_properties(self):
        """Get assigned properties"""
        from apps.properties.models import Property
        if self.permission_level == 'FULL' and self.owner:
            return Property.objects.filter(owner=self.owner)
        return Property.objects.filter(
            caretaker_assignments__caretaker=self,
            caretaker_assignments__is_active=True
        )
    
    def has_permission(self, level):
        """Check if caretaker has the required permission level"""
        levels = ['BASIC', 'STANDARD', 'FULL']
        if self.permission_level in levels:
            return levels.index(self.permission_level) >= levels.index(level)
        return False

    
    def get_user_full_name(self):
        """Get user full name safely"""
        if self.user:
            return self.user.get_full_name() or self.user.email
        return "Unknown User"
    
    def get_user_email(self):
        """Get user email safely"""
        if self.user:
            return self.user.email
        return "No Email"
    
    def is_user_verified(self):
        """Check if user email is verified"""
        if self.user:
            return self.user.is_email_verified
        return False
    
    def get_user_initial(self):
        """Get user initial for avatar"""
        if self.user:
            name = self.user.get_full_name() or self.user.email
            return name[:1].upper()
        return "?"

class CaretakerPropertyAssignment(models.Model):
    """Through model for caretaker-property assignments"""
    caretaker = models.ForeignKey(CaretakerProfile, on_delete=models.CASCADE, related_name='property_assignments')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='caretaker_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'caretaker_property_assignments'
        unique_together = ['caretaker', 'property']
    
    def __str__(self):
        return f"{self.caretaker.user.get_full_name()} - {self.property.title}"


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=200, blank=True)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_suspicious = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'login_history'
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"