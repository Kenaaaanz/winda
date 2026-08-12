from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TenantApplication, Lease
from apps.notifications.models import Notification

@receiver(post_save, sender=TenantApplication)
def notify_owner_on_application(sender, instance, created, **kwargs):
    """Notify property owner when a new application is submitted"""
    if created:
        owner = instance.property.owner.user
        Notification.objects.create(
            user=owner,
            notification_type='APPLICATION',
            title='New Tenant Application',
            message=f'{instance.tenant.get_full_name()} has applied for {instance.property.title}',
            related_object_type='application',
            related_object_id=str(instance.id)
        )

@receiver(post_save, sender=TenantApplication)
def update_application_status(sender, instance, **kwargs):
    """Notify tenant when application status changes"""
    if instance.id:
        try:
            old_instance = TenantApplication.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                # Status changed
                Notification.objects.create(
                    user=instance.tenant,
                    notification_type='APPLICATION',
                    title=f'Application {instance.get_status_display()}',
                    message=f'Your application for {instance.property.title} is now {instance.get_status_display()}',
                    related_object_type='application',
                    related_object_id=str(instance.id)
                )
        except:
            pass

@receiver(post_save, sender=Lease)
def create_lease_notification(sender, instance, created, **kwargs):
    """Create notifications when a lease is created or updated"""
    if created:
        # Notify tenant
        Notification.objects.create(
            user=instance.tenant,
            notification_type='LEASE',
            title='New Lease Created',
            message=f'Your lease for {instance.property.title} has been created',
            related_object_type='lease',
            related_object_id=str(instance.id)
        )
        
        # Notify owner
        Notification.objects.create(
            user=instance.property.owner.user,
            notification_type='LEASE',
            title='New Lease Created',
            message=f'Lease created for {instance.tenant.get_full_name()} at {instance.property.title}',
            related_object_type='lease',
            related_object_id=str(instance.id)
        )