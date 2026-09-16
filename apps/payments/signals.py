from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment, Invoice, ScoutCommission
from apps.notifications.models import Notification
from django.utils import timezone
from decimal import Decimal
from .services import PaymentService

@receiver(post_save, sender=Payment)
def create_payment_notification(sender, instance, created, **kwargs):
    """Create notification when payment is created or updated"""
    if created:
        # Notify payer
        Notification.objects.create(
            user=instance.payer,
            notification_type='PAYMENT',
            title='Payment Initiated',
            message=f'Your payment of {instance.amount} has been initiated',
            related_object_type='payment',
            related_object_id=str(instance.id)
        )
    
    if instance.status == 'COMPLETED':
        if instance.property_id and instance.property.scouted_by_id and instance.platform_fee:
            commission_amount = (instance.platform_fee * Decimal('0.10')).quantize(Decimal('0.01'))
            ScoutCommission.objects.get_or_create(
                payment=instance,
                defaults={
                    'scout_id': instance.property.scouted_by_id,
                    'property_id': instance.property_id,
                    'company_fee': instance.platform_fee,
                    'commission_amount': commission_amount,
                },
            )
        # Completion can be delivered more than once (callback reloads, webhooks,
        # or manual verification), so invoice creation must be idempotent.
        invoice, invoice_created = Invoice.objects.get_or_create(
            payment=instance,
            defaults={
                'user': instance.payer,
                'property': instance.property,
                'invoice_number': PaymentService.generate_invoice_number(),
                'amount': instance.amount,
                'total_amount': instance.amount,
                'due_date': instance.due_date or timezone.now() + timezone.timedelta(days=30),
                'status': 'PAID',
                'paid_date': instance.paid_at or timezone.now(),
            },
        )
        if invoice_created:
            Notification.objects.create(
                user=instance.payer,
                notification_type='PAYMENT',
                title='Payment Successful',
                message=f'Your payment of {instance.amount} was successful',
                related_object_type='payment',
                related_object_id=str(instance.id),
            )

@receiver(post_save, sender=Invoice)
def send_invoice_notification(sender, instance, created, **kwargs):
    """Send notification when invoice is created"""
    if created:
        Notification.objects.create(
            user=instance.user,
            notification_type='PAYMENT',
            title='Invoice Generated',
            message=f'Invoice {instance.invoice_number} has been generated',
            related_object_type='invoice',
            related_object_id=str(instance.id)
        )
