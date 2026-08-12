from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from apps.payments.models import Payment, Invoice
from apps.payments.services import PaymentService
from apps.notifications.models import Notification

class Command(BaseCommand):
    help = 'Fix stuck payments (manually complete pending payments)'
    
    def add_arguments(self, parser):
        parser.add_argument('--reference', type=str, help='Payment reference to fix')
        parser.add_argument('--all', action='store_true', help='Fix all pending payments older than 1 hour')
    
    def handle(self, *args, **options):
        if options.get('reference'):
            # Fix specific payment by reference
            try:
                payment = Payment.objects.get(payment_reference=options['reference'])
                self.fix_payment(payment)
            except Payment.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Payment with reference {options["reference"]} not found'))
        
        elif options.get('all'):
            # Fix all pending payments older than 1 hour
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            payments = Payment.objects.filter(
                status='PENDING',
                created_at__lt=cutoff
            )
            
            count = 0
            for payment in payments:
                self.fix_payment(payment)
                count += 1
            
            self.stdout.write(self.style.SUCCESS(f'Fixed {count} stuck payments'))
        else:
            self.stdout.write(self.style.WARNING('Please specify --reference or --all'))
    
    def fix_payment(self, payment):
        """Fix a single stuck payment"""
        self.stdout.write(f'Fixing payment: {payment.payment_reference}')
        
        # Mark as completed
        payment.status = 'COMPLETED'
        payment.paid_at = timezone.now()
        payment.save()
        
        # Create invoice if it doesn't exist
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
            from apps.payments.views import handle_subscription_payment
            handle_subscription_payment(payment)
        
        # Create notification
        Notification.objects.create(
            user=payment.payer,
            notification_type='PAYMENT',
            title='Payment Fixed',
            message=f'Your payment of KES {payment.amount:,.2f} has been manually completed.',
            related_object_type='payment',
            related_object_id=str(payment.id)
        )
        
        self.stdout.write(self.style.SUCCESS(f'✓ Payment {payment.payment_reference} fixed'))