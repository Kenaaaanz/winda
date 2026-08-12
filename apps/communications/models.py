from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class ChatRoom(models.Model):
    ROOM_TYPES = (
        ('PRIVATE', 'Private'),
        ('GROUP', 'Group'),
        ('PROPERTY_INQUIRY', 'Property Inquiry'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='PRIVATE')
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, null=True, blank=True, related_name='chat_rooms')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_muted = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_rooms'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name or f"Chat {self.id}"
    
    def get_last_message(self):
        return self.messages.filter(is_deleted=False).order_by('-created_at').first()
    
    def get_unread_count(self, user):
        return self.messages.filter(
            is_deleted=False
        ).exclude(read_by=user).count()
    
    def get_other_participant(self, user):
        return self.participants.exclude(id=user.id).first()


class Message(models.Model):
    MESSAGE_TYPES = (
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('FILE', 'File'),
        ('LOCATION', 'Location'),
        ('CONTACT', 'Contact'),
        ('SYSTEM', 'System'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='TEXT')
    content = models.TextField()
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Read receipts
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Deletion
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_messages')
    deleted_for_everyone = models.BooleanField(default=False)
    
    # Reactions
    reactions = models.JSONField(default=dict, blank=True)
    
    # Reply to message
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50]}"
    
    def mark_as_read(self, user):
        if user not in self.read_by.all():
            self.read_by.add(user)
            if self.read_by.count() >= self.room.participants.count() - 1:
                self.read_at = timezone.now()
                self.save()
    
    def get_file_size_display(self):
        if self.file_size:
            size = self.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return "Unknown"
    
    def delete_for_me(self, user):
        """Soft delete message for specific user"""
        # Create a UserMessageDeletion record
        UserMessageDeletion.objects.create(
            user=user,
            message=self,
            deleted_at=timezone.now()
        )
    
    def delete_for_everyone(self, user):
        """Delete message for everyone"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.deleted_for_everyone = True
        self.save()
    
    def is_deleted_for_user(self, user):
        """Check if message is deleted for a specific user"""
        return UserMessageDeletion.objects.filter(
            user=user,
            message=self
        ).exists()


class UserMessageDeletion(models.Model):
    """Track which messages are deleted for which users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_message_deletions'
        unique_together = ['user', 'message']


class MessageTemplate(models.Model):
    TEMPLATE_TYPES = (
        ('WELCOME', 'Welcome Message'),
        ('APPLICATION_RECEIVED', 'Application Received'),
        ('APPLICATION_APPROVED', 'Application Approved'),
        ('APPLICATION_REJECTED', 'Application Rejected'),
        ('PAYMENT_REMINDER', 'Payment Reminder'),
        ('MAINTENANCE_UPDATE', 'Maintenance Update'),
        ('LEASE_EXPIRY', 'Lease Expiry'),
        ('CUSTOM', 'Custom'),
    )
    
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    variables = models.JSONField(default=list, help_text='List of available variables')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'message_templates'
    
    def __str__(self):
        return self.name


class ChatBlock(models.Model):
    """Block users from chatting"""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by_users')
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_blocks'
        unique_together = ['blocker', 'blocked']
    
    def __str__(self):
        return f"{self.blocker.get_full_name()} blocked {self.blocked.get_full_name()}"