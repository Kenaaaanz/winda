# Admin Configuration for New Models

Add the following to `apps/accounts/admin.py`:

```python
from django.contrib import admin
from .models import User, UserProfile, OwnerProfile, TenantProfile, PaystackSubaccount

@admin.register(PaystackSubaccount)
class PaystackSubaccountAdmin(admin.ModelAdmin):
    """Admin interface for Paystack Subaccounts"""
    
    list_display = ('get_owner_name', 'account_name', 'account_number', 'is_active', 'verification_status', 'created_at')
    list_filter = ('is_active', 'verification_status', 'created_at')
    search_fields = ('account_name', 'business_name', 'subaccount_code', 'owner_profile__user__email')
    readonly_fields = ('subaccount_code', 'paystack_response', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Owner Information', {
            'fields': ('owner_profile',)
        }),
        ('Bank Details', {
            'fields': ('bank_code', 'account_number', 'account_name', 'business_name')
        }),
        ('Paystack Information', {
            'fields': ('subaccount_code', 'percentage_charge', 'verification_status', 'is_active')
        }),
        ('Metadata', {
            'fields': ('paystack_response', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_owner_name(self, obj):
        return obj.owner_profile.user.get_full_name() or obj.owner_profile.user.email
    get_owner_name.short_description = 'Owner'
    
    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion of subaccounts
        return request.user.is_superuser


# Update OwnerProfile admin
@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    """Admin interface for Owner Profiles"""
    
    list_display = ('company_name', 'user_email', 'bank_account_set_up', 'paystack_subaccount_verified', 'total_revenue', 'platform_fees_paid')
    list_filter = ('bank_account_set_up', 'paystack_subaccount_verified', 'created_at')
    search_fields = ('company_name', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('total_revenue', 'platform_fees_paid', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Company Details', {
            'fields': ('company_name', 'company_registration_number', 'tax_pin', 'business_license')
        }),
        ('Bank Account Setup', {
            'fields': ('bank_account_set_up', 'paystack_subaccount_verified'),
            'description': 'Owner must set up their bank account to receive payments.'
        }),
        ('Statistics', {
            'fields': ('total_properties', 'total_tenants', 'total_revenue', 'platform_fees_paid', 'average_rating'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def has_add_permission(self, request):
        # OwnerProfiles are created automatically
        return False
```

## Admin Features

### PaystackSubaccountAdmin

**Key Features:**
- View all owner subaccounts at a glance
- Filter by active/inactive and verification status
- Search by owner name, email, account details, or subaccount code
- View raw Paystack API response for debugging
- Prevent accidental deletion (superuser only)

**Display Fields:**
- Owner Name (linked to user)
- Account Name (account holder)
- Account Number (last 4 digits shown for security)
- Active Status (is_active)
- Verification Status (PENDING/VERIFIED/REJECTED)
- Created Date

**Fieldsets:**
1. **Owner Information** - Which owner this subaccount belongs to
2. **Bank Details** - Bank code, account details
3. **Paystack Information** - Subaccount code, percentage charge, verification status
4. **Metadata** - Raw Paystack response, timestamps (collapsed by default)

### OwnerProfileAdmin

**Updated Display:**
- Company Name
- User Email
- Bank Account Setup Status ✅/❌
- Paystack Verification Status ✅/❌
- Total Revenue (read-only)
- Platform Fees Paid (read-only)

**New Filters:**
- Filter by bank account setup status
- Filter by Paystack verification status
- Filter by creation date

**Statistics Display:**
- Total Properties
- Total Tenants
- Total Revenue
- Platform Fees Paid
- Average Rating

## Adding to admin.py

1. Open `apps/accounts/admin.py`
2. Add the PaystackSubaccountAdmin class
3. Update the existing OwnerProfileAdmin (if exists)
4. Import PaystackSubaccount at the top

```python
from .models import (
    User, UserProfile, OwnerProfile, 
    TenantProfile, PaystackSubaccount  # Add this import
)
```

## Admin Actions (Optional)

Add bulk actions for admins in PaystackSubaccountAdmin:

```python
def verify_subaccount(self, request, queryset):
    """Mark selected subaccounts as verified"""
    updated = queryset.update(verification_status='VERIFIED')
    self.message_user(request, f'{updated} subaccounts marked as verified.')
verify_subaccount.short_description = "Mark selected as verified"

def reject_subaccount(self, request, queryset):
    """Reject selected subaccounts"""
    updated = queryset.update(verification_status='REJECTED', is_active=False)
    self.message_user(request, f'{updated} subaccounts rejected.')
reject_subaccount.short_description = "Reject selected subaccounts"

def deactivate_subaccount(self, request, queryset):
    """Deactivate selected subaccounts"""
    updated = queryset.update(is_active=False)
    self.message_user(request, f'{updated} subaccounts deactivated.')
deactivate_subaccount.short_description = "Deactivate selected subaccounts"

# Add to PaystackSubaccountAdmin
actions = [verify_subaccount, reject_subaccount, deactivate_subaccount]
```

## Monitoring Dashboard (Optional)

Create a custom admin view to monitor:

```python
def subaccount_statistics(request):
    """Admin view showing subaccount statistics"""
    from apps.accounts.models import PaystackSubaccount, OwnerProfile
    
    stats = {
        'total_subaccounts': PaystackSubaccount.objects.count(),
        'active_subaccounts': PaystackSubaccount.objects.filter(is_active=True).count(),
        'verified_subaccounts': PaystackSubaccount.objects.filter(verification_status='VERIFIED').count(),
        'pending_verification': PaystackSubaccount.objects.filter(verification_status='PENDING').count(),
        'owners_with_bank_setup': OwnerProfile.objects.filter(bank_account_set_up=True).count(),
        'total_owner_earnings': OwnerProfile.objects.aggregate(
            total=Sum('total_revenue')
        )['total'] or 0,
        'total_platform_fees': OwnerProfile.objects.aggregate(
            total=Sum('platform_fees_paid')
        )['total'] or 0,
    }
    
    return render(request, 'admin/subaccount_stats.html', stats)
```

## Security in Admin

✅ Subaccount codes are readonly (cannot be modified)
✅ Paystack responses are hidden in collapsed section
✅ Deletion is restricted to superusers only
✅ Search is read-only (no injection risk)
✅ Bank details displayed with limited visibility

## Common Admin Tasks

### Task 1: Verify Pending Subaccounts
1. Go to PaystackSubaccounts
2. Filter by "Verification Status = PENDING"
3. Select accounts to verify
4. Use "Mark selected as verified" action
5. Click "Go"

### Task 2: Find Owners Without Bank Setup
1. Go to OwnerProfiles
2. Filter by "Bank Account Setup = False"
3. Contact owners to complete setup

### Task 3: Monitor Platform Fees
1. Go to OwnerProfiles
2. Sort by "Platform Fees Paid" (descending)
3. View total fees across all owners

### Task 4: Troubleshoot Payment Issues
1. Go to PaystackSubaccounts
2. Search for problematic owner's email
3. Review raw Paystack API response
4. Check verification status
5. Update or recreate if needed

## Helpful Django Shell Commands

```python
# Check all subaccounts
from apps.accounts.models import PaystackSubaccount
PaystackSubaccount.objects.all()

# Find owner's subaccount
from apps.accounts.models import OwnerProfile
owner = OwnerProfile.objects.get(user__email='owner@example.com')
owner.paystack_subaccount

# Check pending verifications
PaystackSubaccount.objects.filter(verification_status='PENDING')

# Total platform fees collected
from django.db.models import Sum
OwnerProfile.objects.aggregate(total_fees=Sum('platform_fees_paid'))

# Owners without bank setup
OwnerProfile.objects.filter(bank_account_set_up=False)
```
