from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import OwnerProfile, User
from apps.payments.models import OwnerSubscription, SubscriptionPlan
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

    def test_base_package_uses_three_percent_platform_fee(self):
        fee = PaymentService.get_fee_configuration(Decimal('10000.00'), self.owner_profile)

        self.assertEqual(fee['fee_mode'], 'PERCENTAGE')
        self.assertEqual(fee['platform_fee'], Decimal('300.00'))

    def test_flat_package_charges_once_per_month_then_zero(self):
        plan = SubscriptionPlan.objects.create(
            name='Portfolio Flat',
            plan_type='ENTERPRISE',
            fee_mode='FLAT_RATE',
            monthly_charge=Decimal('500.00'),
            price_monthly=Decimal('5000.00'),
            price_yearly=Decimal('50000.00'),
            minimum_units=1,
        )
        subscription = OwnerSubscription.objects.create(owner=self.owner_profile, plan=plan)

        first_fee = PaymentService.get_fee_configuration(Decimal('10000.00'), self.owner_profile)
        self.assertEqual(first_fee['platform_fee'], Decimal('500.00'))
        self.assertTrue(first_fee['first_flat_charge'])

        subscription.last_flat_fee_month = first_fee['flat_fee_month']
        subscription.save(update_fields=['last_flat_fee_month'])
        later_fee = PaymentService.get_fee_configuration(Decimal('10000.00'), self.owner_profile)
        self.assertEqual(later_fee['platform_fee'], Decimal('0.00'))
        self.assertEqual(later_fee['transaction_charge'], 0)

    def test_flat_package_carries_unpaid_balance(self):
        plan = SubscriptionPlan.objects.create(
            name='Small Flat Balance',
            plan_type='PREMIUM',
            fee_mode='FLAT_RATE',
            monthly_charge=Decimal('500.00'),
            price_monthly=Decimal('5000.00'),
            price_yearly=Decimal('50000.00'),
            minimum_units=1,
        )
        subscription = OwnerSubscription.objects.create(owner=self.owner_profile, plan=plan)

        first_fee = PaymentService.get_fee_configuration(Decimal('200.00'), self.owner_profile)
        self.assertEqual(first_fee['platform_fee'], Decimal('200.00'))
        self.assertEqual(first_fee['flat_fee_balance_after'], Decimal('300.00'))

        subscription.flat_fee_balance = first_fee['flat_fee_balance_after']
        subscription.save(update_fields=['flat_fee_balance'])
        second_fee = PaymentService.get_fee_configuration(Decimal('250.00'), self.owner_profile)
        self.assertEqual(second_fee['platform_fee'], Decimal('250.00'))
        self.assertEqual(second_fee['flat_fee_balance_after'], Decimal('50.00'))


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
