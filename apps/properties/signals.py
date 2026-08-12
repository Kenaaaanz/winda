from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Property, PropertyImage

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