from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from apps.properties.models import Property
from apps.tenants.models import TenantApplication
from apps.payments.models import Payment
from .models import UserActivity

User = get_user_model()

@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log when a user is created"""
    if created:
        UserActivity.objects.create(
            user=instance,
            activity_type='CREATE',
            description=f'User {instance.get_full_name()} registered',
            related_object_type='user',
            related_object_id=str(instance.id)
        )

@receiver(post_save, sender=Property)
def log_property_creation(sender, instance, created, **kwargs):
    """Log when a property is created"""
    if created:
        UserActivity.objects.create(
            user=instance.owner.user,
            activity_type='CREATE',
            description=f'Created property: {instance.title}',
            related_object_type='property',
            related_object_id=str(instance.id)
        )

@receiver(post_save, sender=TenantApplication)
def log_application(sender, instance, created, **kwargs):
    """Log when a tenant application is created"""
    if created:
        UserActivity.objects.create(
            user=instance.tenant,
            activity_type='APPLICATION',
            description=f'Applied for property: {instance.property.title}',
            related_object_type='application',
            related_object_id=str(instance.id)
        )

@receiver(post_save, sender=Payment)
def log_payment(sender, instance, created, **kwargs):
    """Log when a payment is created"""
    if created:
        UserActivity.objects.create(
            user=instance.payer,
            activity_type='PAYMENT',
            description=f'Payment of {instance.amount} initiated',
            related_object_type='payment',
            related_object_id=str(instance.id)
        )