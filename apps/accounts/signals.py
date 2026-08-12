from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile, OwnerProfile, TenantProfile

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        
        if instance.user_type == 'HOUSE_OWNER':
            OwnerProfile.objects.get_or_create(user=instance)
        elif instance.user_type == 'TENANT':
            TenantProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save user profile when user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(post_delete, sender=User)
def delete_user_profile(sender, instance, **kwargs):
    """Delete user profile when user is deleted"""
    if hasattr(instance, 'profile'):
        instance.profile.delete()