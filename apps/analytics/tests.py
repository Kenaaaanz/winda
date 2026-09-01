from django import forms
from django.test import TestCase

from apps.accounts.models import User
from apps.analytics.models import AnalyticsEvent
from apps.properties.models import Property


class AnalyticsEventDeletionTests(TestCase):
    def test_property_deletion_cascades_to_analytics_events(self):
        user = User.objects.create_user(
            username='analytics-owner',
            email='analytics-owner@example.com',
            user_type='HOUSE_OWNER',
        )
        owner = user.owner_profile
        property_record = Property.objects.create(
            owner=owner,
            title='Test property',
            description='Test description',
            property_type='APARTMENT',
            address='Test address',
            city='Nairobi',
            state='Nairobi',
        )
        event = AnalyticsEvent.objects.create(
            event_type='PROPERTY_VIEW',
            property=property_record,
        )

        property_record.delete()

        self.assertFalse(AnalyticsEvent.objects.filter(pk=event.pk).exists())


class AnalyticsFilterForm(forms.Form):
    """Form for filtering analytics data"""
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Start date cannot be later than end date.')
        
        return cleaned_data


class ExportAnalyticsForm(forms.Form):
    """Form for exporting analytics data"""
    EXPORT_TYPES = (
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
    )
    
    export_type = forms.ChoiceField(
        choices=EXPORT_TYPES,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Start date cannot be later than end date.')
        
        return cleaned_data