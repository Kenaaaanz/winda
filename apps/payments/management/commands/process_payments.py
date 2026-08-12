
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import Payment
from apps.payments.services import PaymentService

class Command(BaseCommand):
    help = 'Process pending payments and send reminders'
    
    def handle(self, *args, **options):
        # Find overdue payments
        overdue_payments = Payment.objects.filter(
            status='PENDING',
            due_date__lt=timezone.now()
        )
        
        for payment in overdue_payments:
            days_late = (timezone.now().date() - payment.due_date.date()).days
            late_fee = PaymentService.calculate_late_fee(payment, days_late)
            
            if late_fee > 0:
                payment.amount += late_fee
                payment.metadata['late_fee'] = str(late_fee)
                payment.metadata['days_late'] = days_late
                payment.save()
                
                self.stdout.write(
                    self.style.WARNING(
                        f'Added late fee of {late_fee} to payment {payment.id}'
                    )
                )