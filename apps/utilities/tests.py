import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import OwnerProfile
from apps.properties.models import Property

from .models import UtilityDevice, UtilityReading, UtilityTariff


User = get_user_model()


class UtilityReadingIngestionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='utility-owner@example.com',
            email='utility-owner@example.com',
            password='test-password',
            user_type='HOUSE_OWNER',
            verification_status='VERIFIED',
        )
        owner_profile = OwnerProfile.objects.get(user=self.owner)
        self.property = Property.objects.create(
            owner=owner_profile,
            title='Test building',
            description='Utility test property',
            property_type='APARTMENT',
            furnishing_status='UNFURNISHED',
            address='1 Test Road',
            city='Nairobi',
            state='Nairobi',
        )
        self.tariff = UtilityTariff.objects.create(
            utility='WATER',
            provider='Nairobi City Water',
            unit='m3',
            rate_per_unit=Decimal('12.5000'),
            effective_from=timezone.now() - timedelta(days=1),
        )
        self.api_key = 'test-device-api-key'
        self.device = UtilityDevice.objects.create(
            property=self.property,
            name='Main water meter',
            utility='WATER',
            provider='Nairobi City Water',
            initial_reading=Decimal('100.000'),
            api_key_hash=hashlib.sha256(self.api_key.encode()).hexdigest(),
        )

    def post_reading(self, external_id, meter_value, recorded_at=None, signature_key=None):
        timestamp = str(int(timezone.now().timestamp()))
        payload = {
            'external_id': external_id,
            'meter_value': str(meter_value),
            'recorded_at': (recorded_at or timezone.now()).isoformat(),
        }
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            (signature_key or self.api_key).encode('utf-8'),
            timestamp.encode('ascii') + b'\n' + body,
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            reverse('utilities:ingest_reading', kwargs={'device_id': self.device.id}),
            data=body,
            content_type='application/json',
            secure=True,
            HTTP_X_DEVICE_KEY=self.api_key,
            HTTP_X_DEVICE_TIMESTAMP=timestamp,
            HTTP_X_DEVICE_SIGNATURE=signature,
        )

    def test_signed_reading_uses_baseline_and_effective_tariff(self):
        recorded_at = timezone.now()
        response = self.post_reading('reading-1', '110.000', recorded_at)

        self.assertEqual(response.status_code, 201)
        reading = UtilityReading.objects.get(external_id='reading-1')
        self.assertEqual(reading.usage_delta, Decimal('10.000'))
        self.assertEqual(reading.rate_applied, Decimal('12.5000'))
        self.assertEqual(reading.estimated_cost, Decimal('125.00'))

        second_response = self.post_reading(
            'reading-2',
            '112.000',
            recorded_at + timedelta(seconds=1),
        )
        self.assertEqual(second_response.status_code, 201)
        second_reading = UtilityReading.objects.get(external_id='reading-2')
        self.assertEqual(second_reading.usage_delta, Decimal('2.000'))
        self.assertEqual(second_reading.estimated_cost, Decimal('25.00'))

        self.client.force_login(self.owner)
        dashboard = self.client.get(reverse('utilities:dashboard'), secure=True)
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'KES 150.00')

    def test_owner_dashboard_links_to_utilities(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('dashboard'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('utilities:dashboard'))

    def test_duplicate_reading_id_is_rejected(self):
        recorded_at = timezone.now()
        self.assertEqual(self.post_reading('duplicate', '101.000', recorded_at).status_code, 201)
        response = self.post_reading(
            'duplicate',
            '102.000',
            recorded_at + timedelta(seconds=1),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(UtilityReading.objects.count(), 1)

    def test_invalid_signature_is_rejected(self):
        response = self.post_reading(
            'bad-signature',
            '101.000',
            signature_key='incorrect-key',
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(UtilityReading.objects.exists())

    def test_owner_can_provision_a_meter_and_only_sees_key_once(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('utilities:register_device'),
            {
                'property': str(self.property.id),
                'name': 'Second water meter',
                'utility': 'WATER',
                'provider': 'Nairobi City Water',
                'initial_reading': '0',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        token_page = self.client.get(response.url, secure=True)
        self.assertEqual(token_page.status_code, 200)
        provisioned_device = UtilityDevice.objects.get(name='Second water meter')
        token = token_page.context['device_token']
        self.assertTrue(token)
        self.assertContains(token_page, provisioned_device.id)
        self.assertNotContains(token_page, provisioned_device.api_key_hash)
        self.assertContains(token_page, 'cannot be recovered')
        self.assertNotContains(
            self.client.get(response.url, secure=True),
            token,
        )
