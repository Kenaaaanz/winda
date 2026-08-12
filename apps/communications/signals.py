from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, ChatRoom
from apps.notifications.models import Notification

@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """Create notification when a new message is sent"""
    if created:
        # Notify all participants except sender
        for participant in instance.room.participants.exclude(id=instance.sender.id):
            Notification.objects.create(
                user=participant,
                notification_type='MESSAGE',
                title=f'New message from {instance.sender.get_full_name()}',
                message=instance.content[:100],
                related_object_type='message',
                related_object_id=str(instance.id),
                data={
                    'chat_room_id': str(instance.room.id),
                    'sender_id': str(instance.sender.id),
                    'message_preview': instance.content[:50]
                }
            )

@receiver(post_save, sender=ChatRoom)
def create_chat_notification(sender, instance, created, **kwargs):
    """Create notification when a new chat room is created"""
    if created:
        for participant in instance.participants.all():
            if participant != instance.created_by:
                Notification.objects.create(
                    user=participant,
                    notification_type='MESSAGE',
                    title='New Chat Started',
                    message=f'{instance.created_by.get_full_name()} started a chat with you',
                    related_object_type='chat_room',
                    related_object_id=str(instance.id),
                    data={
                        'chat_room_id': str(instance.id),
                        'created_by': str(instance.created_by.id)
                    }
                )