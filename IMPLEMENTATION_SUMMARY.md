# Quick Reference: 3% Platform Fee Implementation

## Key Changes Summary

### ❌ What's Removed
- Subscription plans (BASIC, PREMIUM, ENTERPRISE)
- Monthly/yearly subscription charges
- Subscription status tracking in OwnerProfile
- Variable platform fees based on plan

### ✅ What's Added
- **PaystackSubaccount Model** - Owner's bank account linked to Paystack
- **Bank Account Setup Flow** - Owners enter their bank details
- **Fixed 3% Platform Fee** - Consistent across all payment types
- **Automatic Fee Calculation** - 3% to Winda, 97% to owner
- **Direct Settlement** - Payments routed to owner's Paystack subaccount

## New Payment Flow

```
Tenant Makes Payment
        ↓
Payment initialized with owner's subaccount code
        ↓
Paystack receives full amount + 3% Winda fee
        ↓
97% settles to owner's subaccount
3% settles to Winda's main account
        ↓
Payment marked as COMPLETED
Owner's revenue updated
        ↓
Notifications sent to tenant & owner
```

## Database Schema Changes

### Modified: OwnerProfile
```
- subscription_status ❌ REMOVED
- subscription_start ❌ REMOVED
- subscription_end ❌ REMOVED
- subscription_plan ❌ REMOVED
+ bank_account_set_up ✅ ADDED
+ paystack_subaccount_verified ✅ ADDED
+ platform_fees_paid ✅ ADDED
+ created_at ✅ ADDED
+ updated_at ✅ ADDED
```

### New: PaystackSubaccount
```
- owner_profile (OneToOne)
- bank_code
- account_number
- account_name
- subaccount_code (from Paystack)
- business_name
- percentage_charge (always 3%)
- is_active
- verification_status
- paystack_response
- created_at, updated_at
```

### Modified: Payment
```
+ platform_fee (3% of amount)
+ owner_amount (97% of amount)
+ paystack_subaccount_code
```

## Code Examples

### 1. Calculate Fee Split
```python
from apps.payments.services import PaymentService
from decimal import Decimal

amount = Decimal('10000.00')
fees = PaymentService.calculate_fee_split(amount)

# Result:
# {
#     'platform_fee': Decimal('300.00'),
#     'owner_amount': Decimal('9700.00'),
#     'platform_percentage': Decimal('3.00'),
#     'owner_percentage': Decimal('97.00')
# }
```

### 2. Create Payment with Subaccount
```python
from apps.payments.models import Payment
from apps.payments.services import PaymentService, PaystackService

# Create payment
payment = Payment.objects.create(
    payer=tenant,
    recipient=owner_user,
    property=property_obj,
    amount=Decimal('10000.00'),
    payment_type='RENT',
    payment_reference='PAY-20240803-ABC123'
)

# Calculate fees
fee_split = PaymentService.calculate_fee_split(payment.amount)
payment.platform_fee = fee_split['platform_fee']
payment.owner_amount = fee_split['owner_amount']

# Get owner's subaccount code
subaccount_code = property_obj.owner.paystack_subaccount.subaccount_code
payment.paystack_subaccount_code = subaccount_code

payment.save()

# Initialize Paystack transaction
paystack = PaystackService()
response = paystack.initialize_transaction_with_subaccount(
    email=tenant.email,
    amount=int(float(payment.amount) * 100),
    reference=payment.payment_reference,
    subaccount_code=subaccount_code
)
```

### 3. Owner Setup Bank Account
```python
from apps.accounts.models import PaystackSubaccount
from apps.payments.services import PaystackService

# Collect form data
bank_code = '001'  # Zenith Bank
account_number = '1234567890'
account_name = 'John Doe'
business_name = 'Doe Properties'

# Create subaccount via Paystack
paystack = PaystackService()
response = paystack.create_subaccount(
    business_name=business_name,
    settlement_bank=bank_code,
    account_number=account_number,
    account_holder_name=account_name,
    percentage_charge=3
)

# Save to database
if response.get('status'):
    PaystackSubaccount.objects.create(
        owner_profile=owner.owner_profile,
        bank_code=bank_code,
        account_number=account_number,
        account_name=account_name,
        subaccount_code=response['data']['subaccount_code'],
        business_name=business_name,
        is_active=True,
        verification_status='VERIFIED',
        paystack_response=response['data']
    )
    
    owner.owner_profile.bank_account_set_up = True
    owner.owner_profile.paystack_subaccount_verified = True
    owner.owner_profile.save()
```

### 4. Payment Verification Callback
```python
from apps.payments.models import Payment
from apps.payments.services import PaymentService, PaystackService

reference = request.GET.get('reference')
paystack = PaystackService()
response = paystack.verify_transaction(reference)

if response.get('status') and response['data']['status'] == 'success':
    payment = Payment.objects.get(payment_reference=reference)
    
    # Mark as completed
    payment.mark_as_completed(reference)
    
    # Ensure fee split is recorded
    if not payment.platform_fee:
        fee_split = PaymentService.calculate_fee_split(payment.amount)
        payment.platform_fee = fee_split['platform_fee']
        payment.owner_amount = fee_split['owner_amount']
        payment.save()
    
    # Update owner profile
    owner = payment.recipient.owner_profile
    owner.total_revenue += payment.owner_amount
    owner.platform_fees_paid += payment.platform_fee
    owner.save()
```

## Views Usage

### Owner Navigation

**Setup Bank Account:**
```
Dashboard → Settings → Bank Account → Setup Bank Account
URL: /accounts/bank-account/setup/
```

**View Account Details:**
```
Dashboard → Settings → Bank Account → Account Details
URL: /accounts/bank-account/
```

**Update Account:**
```
Dashboard → Settings → Bank Account → Update Account
URL: /accounts/bank-account/update/
```

### Payment Statistics

**View Revenue Breakdown:**
```
Dashboard → Finance → Payment Statistics
URL: /payments/stats/
Shows:
- Total Revenue (all payments received)
- Total Platform Fees (3% of revenue)
- Total Owner Earnings (97% of revenue)
- Monthly & Yearly breakdown
```

## Key Constants

```python
# Platform fee percentage
PLATFORM_FEE_PERCENT = Decimal('3.00')

# Owner's earnings percentage
OWNER_PERCENT = Decimal('97.00')

# Payment types that apply fee
APPLICABLE_PAYMENT_TYPES = ['RENT', 'DEPOSIT', 'SERVICE_CHARGE']
```

## Forms

### PaystackSubaccountForm
Located in: `apps/accounts/forms.py`

Includes:
- Bank selection (50+ Nigerian banks)
- Account number validation (min 10 digits)
- Account name
- Business name
- Auto-calculated 3% fee

## Templates Needed

Create the following templates:

1. `templates/accounts/setup_bank_account.html`
   - Bank account setup form
   - Instructions for owners
   - Warnings about requirements

2. `templates/accounts/bank_account_details.html`
   - Display subaccount info
   - Verification status
   - Link to update

3. `templates/accounts/update_bank_account.html`
   - Form to update bank details

4. `templates/payments/stats.html` (UPDATE)
   - Display 3% fee breakdown
   - Show owner earnings vs platform fees
   - Monthly/yearly comparison

## URL Patterns Added

```python
# accounts/urls.py
path('bank-account/setup/', views.setup_bank_account, name='setup_bank_account')
path('bank-account/', views.bank_account_details, name='bank_account_details')
path('bank-account/update/', views.update_bank_account, name='update_bank_account')
```

## Testing Checklist

- [ ] Owner can set up bank account
- [ ] Paystack subaccount is created successfully
- [ ] Payment fee is calculated correctly (3%/97%)
- [ ] Payment routed to owner's subaccount
- [ ] Owner revenue tracking updated after payment
- [ ] Platform fees paid tracking updated
- [ ] Notifications sent to both parties
- [ ] Payment statistics display correct breakdown
- [ ] Bank account can be updated
- [ ] Validation works for all fields

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Subaccount creation failed" | Invalid bank code | Check Paystack bank code list |
| Payments not reaching owner | Owner hasn't set up account | Ensure `bank_account_set_up` is True |
| Fee calculation wrong | Using float instead of Decimal | Always use Decimal type |
| Subaccount code missing | Payment created before subaccount | Verify owner setup before payment |
| Platform fee not updating | Callback not triggered | Check Paystack webhook configuration |

## Backward Compatibility

### Deprecated Endpoints (Still work, show info message)
- `/payments/subscription-plans/` → Redirects to bank setup
- `/payments/cancel-subscription/` → Shows deprecation message

### Deprecated Models (Kept for data integrity)
- SubscriptionPlan table (no longer used)
- Invoice.tax field now stores platform fee instead of 0

## Performance Notes

- PaystackSubaccount is OneToOne (no N+1 queries)
- Consider caching subaccount status if checking on every payment
- Index on `paystack_subaccount_code` for fast lookups
- Payment queries already use `select_related('property__owner')`

## Security Considerations

✅ Bank details validated on server-side
✅ Subaccount codes never exposed to frontend
✅ Paystack API calls use SECRET_KEY (not public)
✅ All fee calculations use Decimal (no floating point errors)
✅ Audit trail maintained via payment history

---

**For detailed migration steps, see:** [MIGRATION_GUIDE_3PERCENT_FEE.md](MIGRATION_GUIDE_3PERCENT_FEE.md)
