# Implementation Checklist: 3% Platform Fee Migration

## Phase 1: Database & Models ✅

### Models Updated
- [x] **OwnerProfile** - Removed subscription fields, added bank setup flags
- [x] **PaystackSubaccount** - New model for bank account management
- [x] **Payment** - Added platform_fee, owner_amount, paystack_subaccount_code fields

### Files Modified
- [x] `apps/accounts/models.py` - OwnerProfile and PaystackSubaccount changes
- [x] `apps/payments/models.py` - Payment model fee tracking

## Phase 2: Business Logic ✅

### Services
- [x] **PaystackService** - Added subaccount management methods:
  - [x] `create_subaccount()`
  - [x] `get_subaccount()`
  - [x] `update_subaccount()`
  - [x] `list_subaccounts()`
  - [x] `initialize_transaction_with_subaccount()`

- [x] **PaymentService** - Added fee calculation:
  - [x] `calculate_fee_split()` - 3%/97% split
  - [x] `PLATFORM_FEE_PERCENT = 3.00` constant

### Files Modified
- [x] `apps/payments/services.py` - PaystackService and PaymentService updates

## Phase 3: Forms & Views ✅

### Forms
- [x] **PaystackSubaccountForm** - Bank account setup form with:
  - [x] Bank selection dropdown (50+ Nigerian banks)
  - [x] Account number validation
  - [x] Account name field
  - [x] Business name field

### Files Modified
- [x] `apps/accounts/forms.py` - Added PaystackSubaccountForm

### Views - Accounts App
- [x] **setup_bank_account()** - Owner sets up Paystack subaccount
- [x] **bank_account_details()** - View bank account info
- [x] **update_bank_account()** - Update bank account details

### Views - Payments App
- [x] **initiate_payment()** - Updated to:
  - [x] Calculate fee split
  - [x] Retrieve owner's subaccount code
  - [x] Use `initialize_transaction_with_subaccount()`
  - [x] Store fee breakdown in Payment

- [x] **payment_callback()** - Updated to:
  - [x] Calculate/verify fee split
  - [x] Update owner's total_revenue
  - [x] Update owner's platform_fees_paid
  - [x] Send fee breakdown notifications
  - [x] Store platform fee in Invoice.tax

- [x] **payment_stats()** - Updated to show:
  - [x] Total revenue
  - [x] Total platform fees (3%)
  - [x] Total owner earnings (97%)
  - [x] Monthly & yearly breakdown

### Deprecated Views
- [x] **subscription_plans()** - Redirects with info message
- [x] **cancel_subscription()** - Shows deprecation message
- [x] **handle_subscription_payment()** - Kept as no-op for backward compatibility

### Files Modified
- [x] `apps/accounts/views.py` - Added bank setup views
- [x] `apps/payments/views.py` - Updated payment views, added OwnerProfile import

## Phase 4: URL Routing ✅

### New URLs
- [x] `accounts/bank-account/setup/` - setup_bank_account
- [x] `accounts/bank-account/` - bank_account_details
- [x] `accounts/bank-account/update/` - update_bank_account

### Files Modified
- [x] `apps/accounts/urls.py` - Added bank account URL patterns

## Phase 5: Documentation ✅

### Documentation Files Created
- [x] `MIGRATION_GUIDE_3PERCENT_FEE.md` - Complete migration guide
- [x] `IMPLEMENTATION_SUMMARY.md` - Quick reference and code examples
- [x] `ADMIN_CONFIGURATION.md` - Admin setup and monitoring
- [x] `IMPLEMENTATION_CHECKLIST.md` (this file)

## Phase 6: Next Steps (Before Deployment)

### Database Migration
- [ ] Run `python manage.py makemigrations accounts payments`
- [ ] Review generated migration files
- [ ] Run `python manage.py migrate`
- [ ] Test migrations in dev environment

### Admin Configuration
- [ ] Add PaystackSubaccountAdmin to `apps/accounts/admin.py`
- [ ] Update OwnerProfileAdmin (optional bulk actions)
- [ ] Test admin interface
- [ ] Test filtering and searching

### Templates Creation
- [ ] Create `templates/accounts/setup_bank_account.html`
  - [ ] Bank account setup form
  - [ ] Instructions for owners
  - [ ] Security notes
  - [ ] Link to Paystack bank codes reference

- [ ] Create `templates/accounts/bank_account_details.html`
  - [ ] Display subaccount info
  - [ ] Show verification status
  - [ ] Link to update
  - [ ] Show status indicators

- [ ] Create `templates/accounts/update_bank_account.html`
  - [ ] Form to update bank details
  - [ ] Warning about account changes
  - [ ] Success/error messages

- [ ] Update `templates/payments/stats.html`
  - [ ] Display 3% fee breakdown
  - [ ] Show owner earnings vs platform fees
  - [ ] Monthly/yearly comparison charts
  - [ ] Clear visualization of fee split

### Testing
- [ ] **Unit Tests**
  - [ ] PaymentService.calculate_fee_split()
  - [ ] Payment model methods
  - [ ] PaystackService subaccount methods

- [ ] **Integration Tests**
  - [ ] Owner bank account setup flow
  - [ ] Payment creation with subaccount
  - [ ] Payment verification and fee tracking
  - [ ] Statistics calculation

- [ ] **Manual Testing**
  - [ ] Owner can set up bank account
  - [ ] Form validation works (account number, etc.)
  - [ ] Paystack subaccount created successfully
  - [ ] Payment initialized with subaccount code
  - [ ] Fee split calculated correctly
  - [ ] Owner revenue tracking updates
  - [ ] Statistics display correctly

### Paystack Configuration
- [ ] Ensure PAYSTACK_SECRET_KEY is set in production
- [ ] Test Paystack API with test/live keys
- [ ] Verify settlement bank codes are available
- [ ] Set up Paystack webhook for payment verification

### Data Migration (Existing Data)
- [ ] Script to update existing payments with fee split
- [ ] Script to update owner profiles
- [ ] Send notifications to owners about bank setup requirement
- [ ] Monitor for orphaned payments without subaccounts

### Deployment Checklist
- [ ] Code review completed
- [ ] All tests passing
- [ ] Documentation reviewed
- [ ] Migrations tested on staging DB
- [ ] Admin interface tested
- [ ] Paystack credentials verified
- [ ] Backup current database
- [ ] Deployment plan documented
- [ ] Rollback plan ready

### Post-Deployment
- [ ] Verify migrations applied successfully
- [ ] Test payment flow end-to-end
- [ ] Monitor error logs for issues
- [ ] Verify owner notifications sent
- [ ] Check Paystack transaction logs
- [ ] Monitor payment statistics accuracy
- [ ] Gather feedback from first few transactions

## Files Summary

### Modified Files
1. `apps/accounts/models.py` - ✅ OwnerProfile and PaystackSubaccount
2. `apps/accounts/forms.py` - ✅ Added PaystackSubaccountForm
3. `apps/accounts/views.py` - ✅ Bank account setup views
4. `apps/accounts/urls.py` - ✅ Bank account URL patterns
5. `apps/payments/models.py` - ✅ Payment fee fields
6. `apps/payments/services.py` - ✅ Subaccount and fee methods
7. `apps/payments/views.py` - ✅ Updated payment flow

### New Documentation Files
1. `MIGRATION_GUIDE_3PERCENT_FEE.md` - Complete migration steps
2. `IMPLEMENTATION_SUMMARY.md` - Quick reference and examples
3. `ADMIN_CONFIGURATION.md` - Admin setup guide
4. `IMPLEMENTATION_CHECKLIST.md` - This checklist

### Files To Create (Templates)
1. `templates/accounts/setup_bank_account.html`
2. `templates/accounts/bank_account_details.html`
3. `templates/accounts/update_bank_account.html`
4. `templates/payments/stats.html` (update existing)

## Key Implementation Details

### Fee Calculation Formula
```
Platform Fee = Amount × 3% = Amount × 0.03
Owner Amount = Amount - Platform Fee = Amount × 0.97
```

### Subaccount Management
- Owner creates ONE subaccount per business
- Subaccount linked via OneToOne relationship
- All owner's payments settle to their subaccount
- 3% fee automatically deducted by Paystack

### Payment Flow
```
Tenant Payment → Paystack Validation → Owner Subaccount Settlement
                                      ↓
                              97% → Owner Bank Account
                              3% → Winda Platform Account
```

### Statistics Tracking
- `Payment.platform_fee` - 3% Winda fee
- `Payment.owner_amount` - 97% owner earnings
- `OwnerProfile.total_revenue` - Sum of all amounts
- `OwnerProfile.platform_fees_paid` - Sum of all platform fees

## Rollback Plan

If issues occur:
1. Stop payment processing
2. Run migrations in reverse
3. Restore from backup
4. Revert code to previous version
5. Test payments with old flow
6. Document issues and fixes
7. Re-deploy with fixes

**Rollback Command:**
```bash
python manage.py migrate accounts <previous_migration_number>
python manage.py migrate payments <previous_migration_number>
git revert <commit_hash>
```

## Support Contact

### For Technical Issues:
- Check `IMPLEMENTATION_SUMMARY.md` for code examples
- Check `MIGRATION_GUIDE_3PERCENT_FEE.md` for detailed steps
- Review Django logs for error messages

### For Admin Questions:
- See `ADMIN_CONFIGURATION.md` for monitoring guide
- Use admin shell commands for debugging

### For Business Logic:
- Review PaymentService methods for fee calculations
- Check PaystackService for API integration details

---

**Status: IMPLEMENTATION COMPLETE** ✅

**Deployment Ready: NO** (awaiting phase 6 completion)

**Last Updated:** 2024-08-03

**Version:** 1.0
