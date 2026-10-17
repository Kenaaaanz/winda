from django import forms
from datetime import timedelta
from decimal import Decimal
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import AnalyticsEvent
from apps.admin_extended.dashboard import dashboard_callback, event_analytics_context
from apps.payments.models import Payment
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


class AdminAnalyticsReportingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='analytics-admin@example.com',
            email='analytics-admin@example.com',
            password='admin-password-123',
        )

    def test_dashboard_payment_kpis_include_historical_completed_payments(self):
        payment = Payment.objects.create(
            payer=self.admin,
            payment_type='RENT',
            amount=Decimal('125000.00'),
            platform_fee=Decimal('2500.00'),
            building_subscription_fee=Decimal('500.00'),
            payment_reference='HISTORIC-ANALYTICS-1',
            due_date=timezone.now(),
            status='COMPLETED',
        )
        old_timestamp = timezone.now() - timedelta(days=180)
        Payment.objects.filter(pk=payment.pk).update(
            created_at=old_timestamp,
            updated_at=old_timestamp,
        )

        request = RequestFactory().get('/admin/')
        request.user = self.admin
        context = dashboard_callback(request, {})
        cards = {card['label']: card for card in context['dashboard']['cards']}

        self.assertEqual(cards['Lifetime payment volume']['value'], Decimal('125000.00'))
        self.assertEqual(cards['Lifetime platform fees']['value'], Decimal('3000.00'))
        self.assertEqual(cards['Completed payments']['value'], 1)
        self.assertEqual(cards['Completed payments']['detail'], '0 completed in the last 30 days')

    def test_payment_completion_event_is_logged_once_on_status_transition(self):
        payment = Payment.objects.create(
            payer=self.admin,
            payment_type='RENT',
            amount=Decimal('1000.00'),
            payment_reference='LIVE-ANALYTICS-1',
            due_date=timezone.now(),
            status='PENDING',
        )
        payment.status = 'COMPLETED'
        payment.paid_at = timezone.now()
        payment.save()

        payment.description = 'Updated after settlement'
        payment.save(update_fields=['description'])

        self.assertEqual(
            AnalyticsEvent.objects.filter(
                user=self.admin,
                event_type='PAYMENT_COMPLETE',
                data__payment_reference=payment.payment_reference,
            ).count(),
            1,
        )

    def test_event_admin_page_shows_live_charts_and_all_history_filter(self):
        AnalyticsEvent.objects.create(
            user=self.admin,
            session_id='analytics-session',
            event_type='PROPERTY_VIEW',
        )
        self.client = Client()
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('admin:analytics_analyticsevent_changelist'),
            {'period': 'all'},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Event intelligence')
        self.assertContains(response, 'Event mix')
        self.assertContains(response, 'Nested event trends')
        self.assertContains(response, 'Total event trend')
        self.assertContains(response, 'All recorded history')
        self.assertContains(response, 'Property View')
        self.assertContains(response, 'Last 15 minutes')

    def test_event_analytics_rejects_unknown_period_and_defaults_to_thirty_days(self):
        AnalyticsEvent.objects.create(user=self.admin, event_type='USER_LOGIN')

        context = event_analytics_context('not-a-period')

        self.assertEqual(context['period'], '30d')
        self.assertEqual(context['total'], AnalyticsEvent.objects.count())


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