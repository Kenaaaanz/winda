from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import NotificationPreference

User = get_user_model()


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences when user is created"""
    if created:
        # Since notification_preferences is now JSONField, just set default values
        if not instance.notification_preferences:
            instance.notification_preferences = {
                'email_application_updates': True,
                'email_payment_notifications': True,
                'email_maintenance_updates': True,
                'email_messages': True,
                'email_marketing': False,
                'sms_application_updates': False,
                'sms_payment_notifications': True,
                'sms_maintenance_updates': False,
                'push_application_updates': True,
                'push_payment_notifications': True,
                'push_messages': True,
                'daily_digest': True,
                'weekly_digest': True,
            }
            instance.save(update_fields=['notification_preferences'])