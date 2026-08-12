from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import OwnerProfile, User
from apps.payments.services import PaymentService, PaystackService
from apps.properties.models import Property


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='StrongPass123!',
            first_name='Owner',
            last_name='User',
            user_type='HOUSE_OWNER',
        )
        self.owner_profile, _ = OwnerProfile.objects.get_or_create(
            user=self.user,
            defaults={'company_name': 'Test Holdings'},
        )
        self.property = Property.objects.create(
            owner=self.owner_profile,
            title='Sunny Apartment',
            description='A test property',
            property_type='APARTMENT',
            furnishing_status='FURNISHED',
            address='123 Main Street',
            city='Nairobi',
            state='Nairobi',
            country='Kenya',
            rental_price=Decimal('15000.00'),
            service_charge=Decimal('1200.00'),
            security_deposit=Decimal('30000.00'),
            bedrooms=2,
            bathrooms=1,
        )

    def test_property_payment_amount_is_based_on_payment_type(self):
        self.assertEqual(
            PaymentService.get_property_payment_amount(self.property, 'RENT'),
            Decimal('15000.00'),
        )
        self.assertEqual(
            PaymentService.get_property_payment_amount(self.property, 'SERVICE_CHARGE'),
            Decimal('1200.00'),
        )
        self.assertEqual(
            PaymentService.get_property_payment_amount(self.property, 'DEPOSIT'),
            Decimal('30000.00'),
        )


class PaystackServiceTests(TestCase):
    @patch('apps.payments.services.requests.request')
    def test_initialize_transaction_uses_paystack_api(self, mock_request):
        mock_response = mock_request.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'data': {'authorization_url': 'https://checkout.paystack.com/fty5okio40k7pq4'}
        }

        service = PaystackService()
        response = service.initialize_transaction(
            email='tenant@example.com',
            amount=50000,
            reference='REF-001-TEST',
            metadata={'payment_type': 'RENT'}
        )

        self.assertIn('data', response)
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args.args[1], 'https://api.paystack.co/transaction/initialize')
        self.assertEqual(mock_request.call_args.kwargs['json']['email'], 'tenant@example.com')
        self.assertEqual(mock_request.call_args.kwargs['json']['amount'], 50000)
        self.assertEqual(mock_request.call_args.kwargs['json']['reference'], 'REF-001-TEST')
