# Migration Guide: Subscription Plans to 3% Platform Fee Model

## Overview
This migration replaces the subscription-based model with a unified 3% platform fee model where:
- **Owners receive 97% of all payments** (rent, service charges, deposits)
- **Winda receives 3% of all transactions** as a platform fee
- Owners must set up their bank account via Paystack subaccount to receive payments

## Changes Made

### 1. Database Models

#### **OwnerProfile Changes**
- ❌ REMOVED: `subscription_status`, `subscription_start`, `subscription_end`, `subscription_plan`
- ✅ ADDED: `bank_account_set_up` (Boolean)
- ✅ ADDED: `paystack_subaccount_verified` (Boolean)
- ✅ ADDED: `platform_fees_paid` (Decimal) - tracks total 3% fees paid by owner
- ✅ ADDED: `created_at`, `updated_at` timestamps

#### **New PaystackSubaccount Model**
```python
- owner_profile (OneToOneField) - Links to OwnerProfile
- bank_code (CharField) - Paystack bank code
- account_number (CharField) - Bank account number
- account_name (CharField) - Account holder name
- subaccount_code (CharField) - Unique Paystack subaccount code
- business_name (CharField) - Owner's business name
- percentage_charge (DecimalField) - Fixed at 3%
- is_active (Boolean)
- verification_status (CharField) - PENDING, VERIFIED, REJECTED
- paystack_response (JSONField) - Stores Paystack API response
- created_at, updated_at timestamps
```

#### **Payment Model Changes**
- ✅ ADDED: `platform_fee` (Decimal) - 3% of amount
- ✅ ADDED: `owner_amount` (Decimal) - 97% of amount
- ✅ ADDED: `paystack_subaccount_code` (CharField) - Paystack subaccount for settlement

### 2. Services Layer

#### **PaystackService - New Methods**
- `create_subaccount()` - Create Paystack subaccount for owner
- `get_subaccount()` - Retrieve subaccount details
- `update_subaccount()` - Update subaccount information
- `list_subaccounts()` - List all subaccounts
- `initialize_transaction_with_subaccount()` - Process payment to specific subaccount

#### **PaymentService - New Methods**
- `calculate_fee_split()` - Calculate 3% platform fee and 97% owner amount
- Static constant: `PLATFORM_FEE_PERCENT = Decimal('3.00')`

### 3. Views Changes

#### **New Bank Account Setup Views** (accounts app)
- `setup_bank_account()` - Owner sets up bank account
- `bank_account_details()` - View bank account information
- `update_bank_account()` - Modify bank account details

#### **Payment Views Updates**
- `initiate_payment()` - Now calculates fee split and uses subaccount code
- `payment_callback()` - Updated to:
  - Calculate and store fee breakdown
  - Update owner's `total_revenue` and `platform_fees_paid`
  - Send fee breakdown notifications
  - Create tax record in Invoice (platform fee)

#### **Deprecated Views**
- `subscription_plans()` - Shows info message, redirects to bank setup
- `cancel_subscription()` - Shows info message
- `handle_subscription_payment()` - Kept but does nothing (backward compatibility)

#### **Updated Payment Stats**
- `payment_stats()` - Now shows:
  - Total revenue
  - Total platform fees (3%)
  - Total owner earnings (97%)
  - Monthly and yearly breakdowns

### 4. Forms

#### **PaystackSubaccountForm** (accounts app)
- Bank selection dropdown with 50+ Nigerian banks
- Account number validation
- Account name
- Business name
- Auto-calculates percentage charge (3%)

### 5. URL Routes

**New account URLs:**
- `/accounts/bank-account/setup/` - Setup bank account
- `/accounts/bank-account/` - View bank account details
- `/accounts/bank-account/update/` - Update bank account

## Migration Steps

### Step 1: Create and Apply Database Migrations

```bash
# Generate migration files for model changes
python manage.py makemigrations accounts payments

# Apply migrations
python manage.py migrate
```

### Step 2: Update Django Admin (Optional)

Add new models to admin.py:
```python
from apps.accounts.models import PaystackSubaccount

@admin.register(PaystackSubaccount)
class PaystackSubaccountAdmin(admin.ModelAdmin):
    list_display = ('owner_profile', 'account_name', 'is_active', 'verification_status')
    list_filter = ('is_active', 'verification_status')
    search_fields = ('account_name', 'business_name', 'subaccount_code')
    readonly_fields = ('subaccount_code', 'paystack_response', 'created_at', 'updated_at')
```

### Step 3: Owner Action Items

1. **Setup Bank Account:**
   - Navigate to `/accounts/bank-account/setup/`
   - Enter bank details (bank, account number, account name)
   - System will create Paystack subaccount
   - Status will change to "VERIFIED" when approved

2. **Verify Setup:**
   - Check `/accounts/bank-account/` for status
   - Ensure `bank_account_set_up` and `paystack_subaccount_verified` are True

### Step 4: Update Payment Processing

All new payments automatically:
- Calculate 3% platform fee
- Route 97% to owner's subaccount
- Store fee breakdown in Payment model
- Update owner's total_revenue and platform_fees_paid

### Step 5: Testing

#### Test Scenario 1: Owner Bank Setup
```python
# Create test owner and set up bank account
owner_user = User.objects.create_user(
    email='owner@test.com',
    user_type='HOUSE_OWNER',
    password='test123'
)
owner_profile = owner_user.owner_profile

# Simulate bank setup
form_data = {
    'bank_code': '001',  # Zenith Bank
    'account_number': '1234567890',
    'account_name': 'John Doe',
    'business_name': 'Doe Properties'
}

# This will call PaystackService.create_subaccount()
```

#### Test Scenario 2: Payment with Fee Split
```python
# Create payment
payment = Payment.objects.create(
    payer=tenant,
    recipient=owner_user,
    property=property_obj,
    amount=Decimal('10000.00'),
    payment_type='RENT'
)

# Calculate fees
fee_split = PaymentService.calculate_fee_split(payment.amount)
# fee_split = {
#     'platform_fee': Decimal('300.00'),  # 3%
#     'owner_amount': Decimal('9700.00'),  # 97%
#     'platform_percentage': Decimal('3.00'),
#     'owner_percentage': Decimal('97.00')
# }

payment.platform_fee = fee_split['platform_fee']
payment.owner_amount = fee_split['owner_amount']
payment.save()
```

## Data Migration (Existing Subscriptions)

### For Existing Owners with Subscriptions:
```python
# Script to migrate existing subscriptions
from apps.accounts.models import OwnerProfile

for owner in OwnerProfile.objects.exclude(subscription_status='CANCELLED'):
    # Set bank account flags to False initially
    owner.bank_account_set_up = False
    owner.paystack_subaccount_verified = False
    owner.platform_fees_paid = Decimal('0.00')
    owner.save()
    
    # Send notification to owner
    # "Your account is ready! Please set up your bank account to receive payments."
```

### For Existing Payments:
```python
# Update existing payments to reflect fee split
from apps.payments.models import Payment
from apps.payments.services import PaymentService

for payment in Payment.objects.filter(status='COMPLETED', platform_fee__isnull=True):
    fee_split = PaymentService.calculate_fee_split(payment.amount)
    payment.platform_fee = fee_split['platform_fee']
    payment.owner_amount = fee_split['owner_amount']
    payment.save()
    
    # Update owner profile
    if payment.recipient and hasattr(payment.recipient, 'owner_profile'):
        owner = payment.recipient.owner_profile
        owner.total_revenue += payment.owner_amount
        owner.platform_fees_paid += payment.platform_fee
        owner.save()
```

## Configuration

### Ensure Paystack Settings
In `settings.py`:
```python
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
```

### Environment Variables
```bash
PAYSTACK_PUBLIC_KEY=pk_live_xxxxx
PAYSTACK_SECRET_KEY=sk_live_xxxxx
```

## Rollback Plan

If needed to rollback:
```bash
# Reverse migrations
python manage.py migrate accounts <previous_migration_number>
python manage.py migrate payments <previous_migration_number>
```

## Support & Troubleshooting

### Issue: Owner's bank account setup fails
- **Solution:** Ensure PAYSTACK_SECRET_KEY is correctly set
- Check Paystack API documentation for settlement_bank codes
- Verify account number is valid

### Issue: Payments not going to subaccount
- **Solution:** Ensure `paystack_subaccount_code` is stored in Payment model
- Check that owner has `paystack_subaccount_verified = True`
- Test with `PaystackService.get_subaccount()` to verify subaccount is active

### Issue: Fee calculation incorrect
- **Solution:** Always use `PaymentService.calculate_fee_split()` for calculations
- Ensure Decimal type is used (not float) to avoid rounding errors

## Security Notes

1. Bank account details are sensitive - use HTTPS only
2. Paystack subaccount codes should not be exposed to frontend
3. Validate all bank details on the server side
4. Log all subaccount creation/updates for audit trail

## Performance Considerations

- PaystackSubaccount is OneToOne with OwnerProfile (no N+1 queries)
- Payment queries on owner already filtered by property.owner
- Consider indexing on `paystack_subaccount_code` for lookups
- Cache subaccount status if checking frequently

## Summary of Benefits

✅ Simplified payment model - no subscription tiers
✅ Transparent fee structure - always 3%
✅ Direct settlement - funds go to owner's subaccount
✅ Scalable - works for unlimited properties and tenants
✅ Compliance - clear audit trail of fees
✅ Better UX - owners see exactly what they earn
