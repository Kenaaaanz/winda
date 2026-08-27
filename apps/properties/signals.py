from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from .models import Property, PropertyImage, Unit
from apps.analytics.models import AnalyticsEvent


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
        # Delete using property_id directly
        AnalyticsEvent.objects.filter(property_id=instance.id).delete()
    except Exception as e:
        print(f"Error clearing analytics events for property {instance.id}: {e}")


@receiver(pre_delete, sender=Unit)
def clear_analytics_events_on_unit_delete(sender, instance, **kwargs):
    """Clear analytics events reference before deleting unit"""
    try:
        # Delete using unit_id directly
        AnalyticsEvent.objects.filter(unit_id=instance.id).delete()
    except Exception as e:
        print(f"Error clearing analytics events for unit {instance.id}: {e}")
