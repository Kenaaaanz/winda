from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Property, PropertyImage
from django.db.models.signals import pre_delete

@receiver(post_save, sender=Property)
def update_owner_stats_on_save(sender, instance, created, **kwargs):
    """Update owner statistics when property is created/updated"""
    from apps.accounts.models import OwnerProfile
    try:
        owner = instance.owner
        owner.total_properties = Property.objects.filter(owner=owner).count()
        owner.save()
    except:
        pass

@receiver(post_delete, sender=Property)
def update_owner_stats_on_delete(sender, instance, **kwargs):
    """Update owner statistics when property is deleted"""
    from apps.accounts.models import OwnerProfile
    try:
        owner = instance.owner
        owner.total_properties = Property.objects.filter(owner=owner).count()
        owner.save()
    except:
        pass

@receiver(post_save, sender=PropertyImage)
def update_main_image(sender, instance, created, **kwargs):
    """Update main image when a new image is added"""
    if created and instance.is_main:
        # Unset other main images
        instance.property.property_images.filter(is_main=True).exclude(id=instance.id).update(is_main=False)

@receiver(pre_delete, sender=Property)
def clear_analytics_events_on_property_delete(sender, instance, **kwargs):
    """Clear analytics events reference before deleting property"""
    try:
        # Set all related analytics events to have null property
        instance.analytics_events.all().update(property=None)
    except Exception as e:
        # Log error but don't prevent deletion
        print(f"Error clearing analytics events: {e}")
