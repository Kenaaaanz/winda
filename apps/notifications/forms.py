from django import forms
from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_application_updates', 'email_payment_notifications',
            'email_maintenance_updates', 'email_messages', 'email_marketing',
            'sms_application_updates', 'sms_payment_notifications',
            'sms_maintenance_updates',
            'push_application_updates', 'push_payment_notifications',
            'push_messages',
            'daily_digest', 'weekly_digest'
        ]
        widgets = {
            'email_application_updates': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'email_payment_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'email_maintenance_updates': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'email_messages': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'email_marketing': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'sms_application_updates': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'sms_payment_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'sms_maintenance_updates': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'push_application_updates': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'push_payment_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'push_messages': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'daily_digest': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'weekly_digest': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add labels for better display
        self.fields['email_application_updates'].label = 'Email - Application Updates'
        self.fields['email_payment_notifications'].label = 'Email - Payment Notifications'
        self.fields['email_maintenance_updates'].label = 'Email - Maintenance Updates'
        self.fields['email_messages'].label = 'Email - Messages'
        self.fields['email_marketing'].label = 'Email - Marketing Communications'
        self.fields['sms_application_updates'].label = 'SMS - Application Updates'
        self.fields['sms_payment_notifications'].label = 'SMS - Payment Notifications'
        self.fields['sms_maintenance_updates'].label = 'SMS - Maintenance Updates'
        self.fields['push_application_updates'].label = 'Push - Application Updates'
        self.fields['push_payment_notifications'].label = 'Push - Payment Notifications'
        self.fields['push_messages'].label = 'Push - Messages'
        self.fields['daily_digest'].label = 'Receive Daily Digest'
        self.fields['weekly_digest'].label = 'Receive Weekly Digest'