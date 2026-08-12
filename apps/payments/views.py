from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
import uuid
from django.conf import settings


from .models import Payment, SubscriptionPlan, Invoice
from .forms import PaymentForm, SubscriptionForm
from .services import PaystackService, PaymentService
from ..accounts.decorators import owner_required, tenant_required
from ..accounts.models import OwnerProfile
from ..properties.models import Property
from ..notifications.models import Notification
from ..tenants.models import Lease
from django.contrib.auth import get_user_model



@login_required
def payment_list(request):
    """List user's payments"""
    payments = Payment.objects.filter(
        Q(payer=request.user) | Q(recipient=request.user)
    ).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        payments = payments.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter and type_filter != 'all':
        payments = payments.filter(payment_type=type_filter)
    
    # Calculate totals BEFORE pagination
    total_completed = payments.filter(status='COMPLETED').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    pending_count = payments.filter(status='PENDING').count()
    
    # Get all payment amounts for the template (without slicing)
    all_payments = payments.all()
    
    # Calculate sum of all amounts (for display)
    total_all_amount = all_payments.aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Pagination (after calculating totals)
    paginator = Paginator(payments, 20)
    page = request.GET.get('page')
    try:
        payments_page = paginator.page(page)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    return render(request, 'payments/list.html', {
        'payments': payments_page,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'total_completed': total_completed,
        'pending_count': pending_count,
        'total_all_amount': total_all_amount,  # Add this
        'payment_types': Payment.PAYMENT_TYPES,
        'status_choices': Payment.PAYMENT_STATUS,
    })

@login_required
def payment_detail(request, payment_id):
    """View payment details"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check permission - allow if user is payer, recipient, or superuser
    if payment.payer != request.user and payment.recipient != request.user:
        if not request.user.is_superuser:
            # Check if user is the owner of the property
            if payment.property and hasattr(request.user, 'owner_profile'):
                if payment.property.owner != request.user.owner_profile:
                    messages.error(request, 'You do not have permission to view this payment.')
                    return redirect('payments:list')
            else:
                messages.error(request, 'You do not have permission to view this payment.')
                return redirect('payments:list')
    
    # Check if user is the property owner
    is_owner = False
    if payment.property and hasattr(request.user, 'owner_profile'):
        if payment.property.owner == request.user.owner_profile:
            is_owner = True
    
    return render(request, 'payments/detail.html', {
        'payment': payment,
        'debug': settings.DEBUG,
        'is_owner': is_owner,
    })


@login_required
@owner_required
@require_http_methods(["POST"])
def approve_payment_manual(request, payment_id):
    """Manually approve a pending payment (Owner only)"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check if user is the property owner
    if payment.property:
        if payment.property.owner != request.user.owner_profile:
            return JsonResponse({'status': 'error', 'message': 'You do not own this property.'}, status=403)
    else:
        # If no property, only superuser can approve
        if not request.user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'Only superusers can approve this payment.'}, status=403)
    
    if payment.status == 'COMPLETED':
        return JsonResponse({'status': 'error', 'message': 'This payment is already completed.'}, status=400)
    
    if payment.status == 'REFUNDED':
        return JsonResponse({'status': 'error', 'message': 'This payment has been refunded.'}, status=400)
    
    # Mark as completed
    payment.status = 'COMPLETED'
    payment.paid_at = timezone.now()
    payment.payment_method = 'MANUAL_APPROVAL'
    payment.metadata['approved_by'] = str(request.user.id)
    payment.metadata['approved_at'] = timezone.now().isoformat()
    payment.metadata['manual_approval'] = True
    payment.save()
    
    # Check if invoice already exists before creating
    if not hasattr(payment, 'invoice'):
        Invoice.objects.create(
            payment=payment,
            user=payment.payer,
            invoice_number=PaymentService.generate_invoice_number(),
            amount=payment.amount,
            tax=Decimal('0'),
            total_amount=payment.amount,
            due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
            status='PAID',
            paid_date=timezone.now()
        )
    
    # Handle subscription if applicable
    if payment.payment_type == 'SUBSCRIPTION':
        handle_subscription_payment(payment)
    
    # Create notification for payer
    Notification.objects.create(
        user=payment.payer,
        notification_type='PAYMENT',
        title='Payment Approved',
        message=f'Your payment of KES {payment.amount:,.2f} has been manually approved.',
        related_object_type='payment',
        related_object_id=str(payment.id)
    )
    
    return JsonResponse({
        'status': 'success',
        'message': 'Payment approved successfully!'
    })

@login_required
@owner_required
@require_http_methods(["POST"])
def reject_payment_manual(request, payment_id):
    """Reject a pending payment (Owner only)"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check if user is the property owner
    if payment.property:
        if payment.property.owner != request.user.owner_profile:
            return JsonResponse({'status': 'error', 'message': 'You do not own this property.'}, status=403)
    
    if payment.status == 'COMPLETED':
        return JsonResponse({'status': 'error', 'message': 'This payment is already completed.'}, status=400)
    
    if payment.status == 'REFUNDED':
        return JsonResponse({'status': 'error', 'message': 'This payment has been refunded.'}, status=400)
    
    # Mark as failed
    payment.status = 'FAILED'
    payment.failure_reason = 'Rejected by property owner'
    payment.metadata['rejected_by'] = str(request.user.id)
    payment.metadata['rejected_at'] = timezone.now().isoformat()
    payment.save()
    
    # Create notification for payer
    Notification.objects.create(
        user=payment.payer,
        notification_type='PAYMENT',
        title='Payment Rejected',
        message=f'Your payment of KES {payment.amount:,.2f} has been rejected by the property owner.',
        related_object_type='payment',
        related_object_id=str(payment.id)
    )
    
    return JsonResponse({
        'status': 'success',
        'message': 'Payment rejected successfully!'
    })


@login_required
@owner_required
@require_http_methods(["POST"])
def sync_payment_paystack(request, payment_id):
    """Sync payment status from Paystack"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check if user is the property owner or superuser
    if payment.property:
        if payment.property.owner != request.user.owner_profile and not request.user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'You do not own this property.'}, status=403)
    
    if payment.status == 'COMPLETED':
        return JsonResponse({'status': 'error', 'message': 'This payment is already completed.'}, status=400)
    
    # Verify with Paystack
    paystack_service = PaystackService()
    response = paystack_service.verify_transaction(payment.payment_reference)
    
    if response.get('status'):
        data = response.get('data', {})
        
        if data.get('status') == 'success':
            # Payment is successful
            payment.status = 'COMPLETED'
            payment.paid_at = timezone.now()
            payment.save()
            
            # Check if invoice already exists before creating
            if not hasattr(payment, 'invoice'):
                Invoice.objects.create(
                    payment=payment,
                    user=payment.payer,
                    invoice_number=PaymentService.generate_invoice_number(),
                    amount=payment.amount,
                    tax=Decimal('0'),
                    total_amount=payment.amount,
                    due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
                    status='PAID',
                    paid_date=timezone.now()
                )
            
            # Handle subscription if applicable
            if payment.payment_type == 'SUBSCRIPTION':
                handle_subscription_payment(payment)
            
            # Create notification
            Notification.objects.create(
                user=payment.payer,
                notification_type='PAYMENT',
                title='Payment Synced',
                message=f'Your payment of KES {payment.amount:,.2f} has been verified and completed.',
                related_object_type='payment',
                related_object_id=str(payment.id)
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment synced successfully! Payment is now completed.'
            })
        else:
            # Payment failed or pending
            return JsonResponse({
                'status': 'warning',
                'message': f'Payment status from Paystack: {data.get("status", "unknown")}'
            })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to verify payment with Paystack. Please try again later.'
        }, status=400)
    

@login_required
@owner_required
def sync_all_payments(request):
    """Sync all pending payments from Paystack"""
    if request.method == 'POST':
        owner = request.user.owner_profile
        pending_payments = Payment.objects.filter(
            property__owner=owner,
            status='PENDING'
        )
        
        synced = 0
        failed = 0
        already_completed = 0
        
        for payment in pending_payments:
            paystack_service = PaystackService()
            response = paystack_service.verify_transaction(payment.payment_reference)
            
            if response.get('status'):
                data = response.get('data', {})
                if data.get('status') == 'success':
                    # Check if payment is already completed
                    if payment.status == 'COMPLETED':
                        already_completed += 1
                        continue
                    
                    # Mark as completed
                    payment.status = 'COMPLETED'
                    payment.paid_at = timezone.now()
                    payment.save()
                    
                    # Check if invoice already exists before creating
                    if not hasattr(payment, 'invoice'):
                        Invoice.objects.create(
                            payment=payment,
                            user=payment.payer,
                            invoice_number=PaymentService.generate_invoice_number(),
                            amount=payment.amount,
                            tax=Decimal('0'),
                            total_amount=payment.amount,
                            due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
                            status='PAID',
                            paid_date=timezone.now()
                        )
                    
                    # Handle subscription if applicable
                    if payment.payment_type == 'SUBSCRIPTION':
                        handle_subscription_payment(payment)
                    
                    synced += 1
                else:
                    failed += 1
            else:
                failed += 1
        
        # Set success message
        messages.success(
            request, 
            f'Sync complete! {synced} payments synced successfully, {failed} failed, {already_completed} already completed.'
        )
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f'Sync complete! {synced} payments synced successfully, {failed} failed, {already_completed} already completed.',
                'data': {
                    'synced': synced,
                    'failed': failed,
                    'already_completed': already_completed,
                    'total_processed': synced + failed + already_completed,
                }
            })
        
        # Regular form submission - redirect to payments list
        return redirect('payments:list')
    
    # GET request - show confirmation page
    owner = request.user.owner_profile
    pending_count = Payment.objects.filter(
        property__owner=owner,
        status='PENDING'
    ).count()
    
    return render(request, 'payments/sync_all.html', {
        'pending_count': pending_count,
    })

@login_required
def initiate_payment(request):
    """Initiate a new payment for rent, service charges, deposits or manual payments."""
    if request.method == 'POST':
        form = PaymentForm(request.POST, user=request.user)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.payer = request.user
            property_obj = form.cleaned_data.get('property')
            payment.recipient = property_obj.owner.user if property_obj else None
            payment.amount = Decimal(str(form.cleaned_data['amount']))
            payment.payment_reference = f"PAY-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            payment.status = 'PENDING'
            
            # Calculate fee split: 3% to Winda, 97% to owner
            fee_split = PaymentService.calculate_fee_split(payment.amount)
            payment.platform_fee = fee_split['platform_fee']
            payment.owner_amount = fee_split['owner_amount']
            
            # Get the owner's Paystack subaccount code
            subaccount_code = None
            if property_obj and property_obj.owner:
                try:
                    subaccount = property_obj.owner.paystack_subaccount
                    if subaccount and subaccount.is_active:
                        subaccount_code = subaccount.subaccount_code
                        payment.paystack_subaccount_code = subaccount_code
                    elif not property_obj.owner.bank_account_set_up:
                        messages.error(request, 'Property owner has not set up their bank account yet. Payment cannot be processed.')
                        return redirect('payments:list')
                except Exception as e:
                    messages.warning(request, f'Could not retrieve owner\'s subaccount: {str(e)}')
            
            payment.save()

            paystack_service = PaystackService()
            response = paystack_service.initialize_transaction_with_subaccount(
                email=request.user.email,
                amount=int(float(payment.amount) * 100),
                reference=payment.payment_reference,
                subaccount_code=subaccount_code,
                metadata={
                    'payment_id': str(payment.id),
                    'user_id': str(request.user.id),
                    'payment_type': payment.payment_type,
                    'property_id': str(payment.property.id) if payment.property else '',
                    'recipient_id': str(payment.recipient.id) if payment.recipient else '',
                    'owner_amount': str(payment.owner_amount),
                    'platform_fee': str(payment.platform_fee),
                }
            ) if subaccount_code else paystack_service.initialize_transaction(
                email=request.user.email,
                amount=int(float(payment.amount) * 100),
                reference=payment.payment_reference,
                metadata={
                    'payment_id': str(payment.id),
                    'user_id': str(request.user.id),
                    'payment_type': payment.payment_type,
                    'property_id': str(payment.property.id) if payment.property else '',
                    'recipient_id': str(payment.recipient.id) if payment.recipient else '',
                    'owner_amount': str(payment.owner_amount),
                    'platform_fee': str(payment.platform_fee),
                }
            )

            if response.get('status'):
                payment.payment_link = response['data']['authorization_url']
                payment.save()
                return redirect(payment.payment_link)

            error_message = response.get('message') or response.get('payload', {}).get('message') or 'Payment initialization failed'
            payment.mark_as_failed(error_message)
            messages.error(request, f'Failed to initiate payment: {error_message}')
    else:
        initial_data = {}
        property_id = request.GET.get('property_id')
        payment_type = request.GET.get('payment_type', 'RENT')
        if property_id:
            property_obj = get_object_or_404(Property, id=property_id)
            initial_data['property'] = property_obj
            initial_data['amount'] = PaymentService.get_property_payment_amount(property_obj, payment_type)
            initial_data['payment_type'] = payment_type
            if payment_type == 'RENT':
                initial_data['description'] = f'Rent for {property_obj.title}'
            elif payment_type == 'SERVICE_CHARGE':
                initial_data['description'] = f'Service charge for {property_obj.title}'
            elif payment_type == 'DEPOSIT':
                initial_data['description'] = f'Security deposit for {property_obj.title}'
            initial_data['due_date'] = timezone.now() + timezone.timedelta(days=30)

        form = PaymentForm(initial=initial_data, user=request.user)

    return render(request, 'payments/initiate.html', {
        'form': form,
    })

@login_required
@require_http_methods(["POST"])
def retry_payment(request, payment_id):
    """Retry a failed payment"""
    payment = get_object_or_404(Payment, id=payment_id, payer=request.user)
    
    # Check if payment can be retried
    if payment.status not in ['FAILED', 'PENDING']:
        return JsonResponse({
            'status': 'error', 
            'message': 'This payment cannot be retried.'
        }, status=400)
    
    # Initialize Paystack transaction
    paystack_service = PaystackService()
    response = paystack_service.initialize_transaction(
        email=request.user.email,
        amount=int(float(payment.amount) * 100),  # Convert to kobo/cents
        reference=payment.payment_reference,
        metadata={
            'payment_id': str(payment.id),
            'user_id': str(request.user.id),
            'payment_type': payment.payment_type,
            'retry': True
        }
    )
    
    if response.get('status'):
        payment.payment_link = response['data']['authorization_url']
        payment.status = 'PENDING'
        payment.save()
        
        return JsonResponse({
            'status': 'success',
            'payment_link': payment.payment_link
        })
    else:
        payment.mark_as_failed(response.get('message', 'Payment retry failed'))
        return JsonResponse({
            'status': 'error',
            'message': response.get('message', 'Failed to retry payment')
        }, status=400)


@login_required
def payment_callback(request):
    """Handle Paystack payment callback"""
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, 'Invalid payment reference.')
        return redirect('payments:list')
    
    try:
        payment = Payment.objects.get(payment_reference=reference)
    except Payment.DoesNotExist:
        messages.error(request, 'Payment not found.')
        return redirect('payments:list')
    
    # Verify transaction with Paystack
    paystack_service = PaystackService()
    response = paystack_service.verify_transaction(reference)
    
    if response.get('status'):
        data = response.get('data', {})
        
        if data.get('status') == 'success':
            # Check if payment is already completed
            if payment.status == 'COMPLETED':
                messages.info(request, 'This payment is already completed.')
                return redirect('payments:detail', payment_id=payment.id)
            
            # Update payment status
            payment.status = 'COMPLETED'
            payment.paid_at = timezone.now()
            payment.save()
            
            # Check if invoice already exists before creating
            if not hasattr(payment, 'invoice'):
                Invoice.objects.create(
                    payment=payment,
                    user=payment.payer,
                    invoice_number=PaymentService.generate_invoice_number(),
                    amount=payment.amount,
                    tax=Decimal('0'),
                    total_amount=payment.amount,
                    due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
                    status='PAID',
                    paid_date=timezone.now()
                )
            
            # If it's a subscription payment, update subscription
            if payment.payment_type == 'SUBSCRIPTION':
                handle_subscription_payment(payment)
            
            # Create success notification
            Notification.objects.create(
                user=payment.payer,
                notification_type='PAYMENT',
                title='Payment Successful',
                message=f'Your payment of KES {payment.amount:,.2f} was successful.',
                related_object_type='payment',
                related_object_id=str(payment.id)
            )
            
            messages.success(request, 'Payment successful!')
            return redirect('payments:detail', payment_id=payment.id)
        else:
            # Payment failed
            payment.status = 'FAILED'
            payment.failure_reason = data.get('gateway_response', 'Payment verification failed')
            payment.save()
            
            messages.error(request, f'Payment failed: {payment.failure_reason}')
            return redirect('payments:detail', payment_id=payment.id)
    else:
        messages.error(request, 'Payment verification failed. Please try again.')
        return redirect('payments:detail', payment_id=payment.id)

@login_required
@owner_required
def verify_payment_manual(request, payment_id):
    """Manually verify a payment (for testing purposes)"""
    payment = get_object_or_404(Payment, id=payment_id, payer=request.user)
    
    if payment.status == 'COMPLETED':
        messages.warning(request, 'This payment is already completed.')
        return redirect('payments:detail', payment_id=payment.id)
    
    if request.method == 'POST':
        # Manually mark as completed
        payment.status = 'COMPLETED'
        payment.paid_at = timezone.now()
        payment.save()
        
        # Check if invoice already exists before creating
        if not hasattr(payment, 'invoice'):
            Invoice.objects.create(
                payment=payment,
                user=payment.payer,
                invoice_number=PaymentService.generate_invoice_number(),
                amount=payment.amount,
                tax=Decimal('0'),
                total_amount=payment.amount,
                due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
                status='PAID',
                paid_date=timezone.now()
            )
        
        # If it's a subscription payment, update subscription
        if payment.payment_type == 'SUBSCRIPTION':
            handle_subscription_payment(payment)
        
        # Create success notification
        Notification.objects.create(
            user=payment.payer,
            notification_type='PAYMENT',
            title='Payment Verified',
            message=f'Payment of KES {payment.amount:,.2f} has been manually verified.',
            related_object_type='payment',
            related_object_id=str(payment.id)
        )
        
        messages.success(request, 'Payment manually verified successfully!')
        return redirect('payments:detail', payment_id=payment.id)
    
    return render(request, 'payments/verify_manual.html', {
        'payment': payment,
    })

def handle_subscription_payment(payment):
    """Handle subscription payment completion - DEPRECATED
    
    Subscriptions are no longer used. All payments are now subject to the 3% platform fee.
    This function is kept for backward compatibility but does nothing.
    """
    pass


@login_required
@owner_required
def subscription_plans(request):
    """Subscription plans view - DEPRECATED
    
    Subscriptions have been removed. All owners now automatically have access to all features.
    Payments are processed with a 3% platform fee.
    """
    messages.info(request, 'Subscription plans are no longer used. You can now accept all types of payments with a 3% platform fee. Please ensure your bank account is set up to receive payments.')
    
    # Check if owner has set up their bank account
    try:
        owner_profile = request.user.owner_profile
        if not owner_profile.bank_account_set_up:
            messages.warning(request, 'Please set up your bank account first to receive payments.')
            return redirect('accounts:setup_bank_account')
    except OwnerProfile.DoesNotExist:
        pass
    
    return redirect('payments:list')


@login_required
@owner_required
def cancel_subscription(request):
    """Cancel subscription - DEPRECATED
    
    Subscriptions are no longer used. This view shows an info message.
    """
    messages.info(request, 'Subscription plans are no longer used. You automatically have access to all features with a 3% platform fee on all payments.')
    return redirect('payments:list')


@login_required
def invoice_list(request):
    """List user's invoices"""
    invoices = Invoice.objects.filter(user=request.user).order_by('-issue_date')
    
    paginator = Paginator(invoices, 20)
    page = request.GET.get('page')
    try:
        invoices_page = paginator.page(page)
    except PageNotAnInteger:
        invoices_page = paginator.page(1)
    except EmptyPage:
        invoices_page = paginator.page(paginator.num_pages)
    
    return render(request, 'payments/invoice_list.html', {
        'invoices': invoices_page,
    })


@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    return render(request, 'payments/invoice_detail.html', {
        'invoice': invoice,
    })


@login_required
def download_invoice(request, invoice_id):
    """Download invoice PDF"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    # Generate PDF if it doesn't exist
    if not invoice.pdf_file:
        invoice.generate_pdf()
    
    if invoice.pdf_file:
        return redirect(invoice.pdf_file.url)
    else:
        messages.error(request, 'Invoice PDF not available.')
        return redirect('payments:invoice_detail', invoice_id=invoice_id)


@login_required
@owner_required
def payment_stats(request):
    """Payment statistics for owner showing 3% platform fee breakdown"""
    owner = request.user.owner_profile
    
    # Get all completed payments for owner's properties
    payments = Payment.objects.filter(
        property__owner=owner,
        status='COMPLETED'
    )
    
    # Monthly stats
    current_month = timezone.now().month
    current_year = timezone.now().year
    monthly_payments = payments.filter(
        paid_at__month=current_month,
        paid_at__year=current_year
    )
    
    # Yearly stats
    yearly_payments = payments.filter(paid_at__year=current_year)
    
    # Calculate totals with fee breakdown
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
    total_platform_fees = payments.aggregate(total=Sum('platform_fee'))['total'] or 0
    total_owner_earnings = payments.aggregate(total=Sum('owner_amount'))['total'] or 0
    
    monthly_revenue = monthly_payments.aggregate(total=Sum('amount'))['total'] or 0
    monthly_platform_fees = monthly_payments.aggregate(total=Sum('platform_fee'))['total'] or 0
    monthly_owner_earnings = monthly_payments.aggregate(total=Sum('owner_amount'))['total'] or 0
    
    yearly_revenue = yearly_payments.aggregate(total=Sum('amount'))['total'] or 0
    yearly_platform_fees = yearly_payments.aggregate(total=Sum('platform_fee'))['total'] or 0
    yearly_owner_earnings = yearly_payments.aggregate(total=Sum('owner_amount'))['total'] or 0
    
    stats = {
        'total_revenue': total_revenue,
        'total_platform_fees': total_platform_fees,
        'total_owner_earnings': total_owner_earnings,
        'monthly_revenue': monthly_revenue,
        'monthly_platform_fees': monthly_platform_fees,
        'monthly_owner_earnings': monthly_owner_earnings,
        'yearly_revenue': yearly_revenue,
        'yearly_platform_fees': yearly_platform_fees,
        'yearly_owner_earnings': yearly_owner_earnings,
        'payment_count': payments.count(),
        'pending_payments': Payment.objects.filter(
            property__owner=owner,
            status='PENDING'
        ).count(),
        'platform_fee_percent': Decimal('3.00'),
    }
    
    return render(request, 'payments/stats.html', stats)

def create_invoice_if_not_exists(payment):
    """Create an invoice for a payment if it doesn't already exist"""
    if not hasattr(payment, 'invoice'):
        try:
            Invoice.objects.create(
                payment=payment,
                user=payment.payer,
                invoice_number=PaymentService.generate_invoice_number(),
                amount=payment.amount,
                tax=Decimal('0'),
                total_amount=payment.amount,
                due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
                status='PAID',
                paid_date=timezone.now()
            )
            return True
        except Exception as e:
            # Log error but don't fail
            print(f"Error creating invoice: {e}")
            return False
    return True
