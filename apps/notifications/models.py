from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('APPLICATION', 'Application Update'),
        ('PAYMENT', 'Payment Notification'),
        ('MAINTENANCE', 'Maintenance Update'),
        ('MESSAGE', 'New Message'),
        ('LEASE', 'Lease Update'),
        ('REMINDER', 'Reminder'),
        ('SYSTEM', 'System Notification'),
        ('PROMOTION', 'Promotion'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    
    # Notification details
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related object
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=50, blank=True)
    
    # Data
    data = models.JSONField(default=dict, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    
    # Delivery methods
    sent_email = models.BooleanField(default=False)
    sent_sms = models.BooleanField(default=False)
    sent_push = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at'])
    
    def archive(self):
        self.is_archived = True
        self.save(update_fields=['is_archived'])
    
    @classmethod
    def get_unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()


from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('APPLICATION', 'Application Update'),
        ('PAYMENT', 'Payment Notification'),
        ('MAINTENANCE', 'Maintenance Update'),
        ('MESSAGE', 'New Message'),
        ('LEASE', 'Lease Update'),
        ('REMINDER', 'Reminder'),
        ('SYSTEM', 'System Notification'),
        ('PROMOTION', 'Promotion'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    
    # Notification details
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related object
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=50, blank=True)
    
    # Data
    data = models.JSONField(default=dict, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    
    # Delivery methods
    sent_email = models.BooleanField(default=False)
    sent_sms = models.BooleanField(default=False)
    sent_push = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at'])
    
    def archive(self):
        self.is_archived = True
        self.save(update_fields=['is_archived'])
    
    @classmethod
    def get_unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='notification_preference_obj'  # Changed to avoid conflict with JSONField
    )
    
    # Email preferences
    email_application_updates = models.BooleanField(default=True)
    email_payment_notifications = models.BooleanField(default=True)
    email_maintenance_updates = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)
    
    # SMS preferences
    sms_application_updates = models.BooleanField(default=False)
    sms_payment_notifications = models.BooleanField(default=True)
    sms_maintenance_updates = models.BooleanField(default=False)
    sms_messages = models.BooleanField(default=True)
    
    # Push notification preferences
    push_application_updates = models.BooleanField(default=True)
    push_payment_notifications = models.BooleanField(default=True)
    push_maintenance_updates = models.BooleanField(default=True)
    push_messages = models.BooleanField(default=True)
    
    # Digest preferences
    daily_digest = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=True)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(default='22:00', null=True, blank=True)
    quiet_hours_end = models.TimeField(default='07:00', null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        user_name = self.user.get_full_name() or self.user.email
        return f"Notification preferences for {user_name}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create notification preferences for a user"""
        preference, created = cls.objects.get_or_create(user=user)
        return preference
    
    def to_dict(self):
        """Convert preferences to dictionary"""
        return {
            'email_application_updates': self.email_application_updates,
            'email_payment_notifications': self.email_payment_notifications,
            'email_maintenance_updates': self.email_maintenance_updates,
            'email_messages': self.email_messages,
            'email_marketing': self.email_marketing,
            'sms_application_updates': self.sms_application_updates,
            'sms_payment_notifications': self.sms_payment_notifications,
            'sms_maintenance_updates': self.sms_maintenance_updates,
            'sms_messages': self.sms_messages,
            'push_application_updates': self.push_application_updates,
            'push_payment_notifications': self.push_payment_notifications,
            'push_maintenance_updates': self.push_maintenance_updates,
            'push_messages': self.push_messages,
            'daily_digest': self.daily_digest,
            'weekly_digest': self.weekly_digest,
            'quiet_hours_enabled': self.quiet_hours_enabled,
            'quiet_hours_start': str(self.quiet_hours_start) if self.quiet_hours_start else None,
            'quiet_hours_end': str(self.quiet_hours_end) if self.quiet_hours_end else None,
        }
    
    def update_from_dict(self, data):
        """Update preferences from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
        return self