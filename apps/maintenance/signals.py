from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MaintenanceRequest
from apps.notifications.models import Notification

@receiver(post_save, sender=MaintenanceRequest)
def create_maintenance_notification(sender, instance, created, **kwargs):
    """Create notification when maintenance request is created or updated"""
    if created:
        # Notify property owner
        owner = instance.property.owner.user
        Notification.objects.create(
            user=owner,
            notification_type='MAINTENANCE',
            title='New Maintenance Request',
            message=f'{instance.tenant.get_full_name()} reported: {instance.title}',
            related_object_type='maintenance',
            related_object_id=str(instance.id)
        )
    else:
        # Check if status changed
        try:
            old_instance = MaintenanceRequest.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                # Notify tenant
                Notification.objects.create(
                    user=instance.tenant,
                    notification_type='MAINTENANCE',
                    title=f'Maintenance Update: {instance.get_status_display()}',
                    message=f'Your request "{instance.title}" is now {instance.get_status_display()}',
                    related_object_type='maintenance',
                    related_object_id=str(instance.id)
                )
                
                # If assigned, notify assigned person
                if instance.assigned_to and instance.status == 'ASSIGNED':
                    Notification.objects.create(
                        user=instance.assigned_to,
                        notification_type='MAINTENANCE',
                        title='Maintenance Assigned',
                        message=f'You have been assigned to: {instance.title}',
                        related_object_type='maintenance',
                        related_object_id=str(instance.id)
                    )
        except:
            pass