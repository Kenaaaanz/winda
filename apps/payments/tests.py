from decimal import Decimal
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import OwnerProfile, ScoutProfile, User
from apps.payments.models import OwnerSubscription, Payment, ScoutCommission, ScoutPayout, SubscriptionPlan
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

    def test_per_building_charge_carries_forward_then_recurs_next_month(self):
        plan = SubscriptionPlan.objects.create(
            name='Building Charge',
            plan_type='ENTERPRISE',
            fee_mode='PER_BUILDING',
            price_monthly=Decimal('0.00'),
            price_yearly=Decimal('0.00'),
            building_threshold=1,
            per_building_charge=Decimal('500.00'),
        )
        OwnerSubscription.objects.create(owner=self.owner_profile, plan=plan)

        first_config = PaymentService.get_fee_configuration(Decimal('200.00'), self.owner_profile)
        self.assertEqual(first_config['platform_fee'], Decimal('0.00'))
        self.assertEqual(first_config['fee_mode'], 'PER_BUILDING')
        billing_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_building_fee = PaymentService.get_building_subscription_fee(
            Decimal('200.00'), self.property, first_config['platform_fee'], at=billing_date,
        )
        self.assertEqual(first_building_fee['fee'], Decimal('200.00'))

        first_payment = Payment.objects.create(
            payer=self.user,
            property=self.property,
            payment_type='RENT',
            amount=Decimal('200.00'),
            platform_fee=first_config['platform_fee'],
            building_subscription_charge=first_building_fee['charge'],
            building_subscription_fee=first_building_fee['fee'],
            payment_reference='BUILDING-CHARGE-FIRST',
            due_date=timezone.now(),
            status='COMPLETED',
        )
        second_config = PaymentService.get_fee_configuration(Decimal('500.00'), self.owner_profile)
        second_building_fee = PaymentService.get_building_subscription_fee(
            Decimal('500.00'), self.property, second_config['platform_fee'], at=billing_date,
        )

        self.assertEqual(second_building_fee['fee'], Decimal('300.00'))
        first_payment.refresh_from_db()
        self.assertEqual(first_payment.building_subscription_charge.amount_due, Decimal('500.00'))

        next_month_fee = PaymentService.get_building_subscription_fee(
            Decimal('1000.00'), self.property, Decimal('30.00'), at=billing_date + timedelta(days=32),
        )
        self.assertEqual(next_month_fee['fee'], Decimal('500.00'))
        self.assertNotEqual(next_month_fee['charge'].id, first_building_fee['charge'].id)

    def test_building_charge_waits_until_owner_reaches_admin_threshold(self):
        plan = SubscriptionPlan.objects.create(
            name='Threshold Building Charge',
            plan_type='ENTERPRISE',
            fee_mode='PER_BUILDING',
            price_monthly=Decimal('0.00'),
            price_yearly=Decimal('0.00'),
            building_threshold=2,
            per_building_charge=Decimal('500.00'),
        )
        OwnerSubscription.objects.create(owner=self.owner_profile, plan=plan)

        result = PaymentService.get_building_subscription_fee(
            Decimal('1000.00'), self.property, Decimal('0.00'),
        )

        self.assertEqual(result['fee'], Decimal('0.00'))
        self.assertIsNone(result['charge'])

    def test_percentage_package_does_not_collect_per_building_charge(self):
        plan = SubscriptionPlan.objects.create(
            name='Percentage Only',
            plan_type='BASIC',
            fee_mode='PERCENTAGE',
            price_monthly=Decimal('0.00'),
            price_yearly=Decimal('0.00'),
            building_threshold=1,
            per_building_charge=Decimal('500.00'),
        )
        OwnerSubscription.objects.create(owner=self.owner_profile, plan=plan)

        result = PaymentService.get_building_subscription_fee(
            Decimal('1000.00'), self.property, Decimal('30.00'),
        )

        self.assertEqual(result['fee'], Decimal('0.00'))
        self.assertIsNone(result['charge'])


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

    @patch.object(PaystackService, '_request')
    def test_create_kenyan_transfer_recipient(self, mock_request):
        mock_request.return_value = {'status': True, 'data': {'recipient_code': 'RCP_test'}}

        response = PaystackService().create_transfer_recipient(
            name='Property Scout',
            account_number='1234567890',
            bank_code='TEST001',
        )

        self.assertTrue(response['status'])
        self.assertEqual(mock_request.call_args.args[:2], ('post', '/transferrecipient'))
        self.assertEqual(mock_request.call_args.kwargs['json']['type'], 'kepss')
        self.assertEqual(mock_request.call_args.kwargs['json']['currency'], 'KES')

    @patch.object(PaystackService, '_request')
    def test_initiate_scout_transfer_converts_kes_to_minor_units(self, mock_request):
        mock_request.return_value = {'status': True, 'data': {'status': 'pending'}}

        PaystackService().initiate_transfer(
            amount=Decimal('125.50'),
            recipient_code='RCP_test',
            reference='scout-0123456789abcdef0123456789abcdef',
            reason='Property scout commission payout',
        )

        payload = mock_request.call_args.kwargs['json']
        self.assertEqual(payload['amount'], 12550)
        self.assertEqual(payload['currency'], 'KES')


class ScoutPayoutTests(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user(
            username='payout-owner@example.com',
            email='payout-owner@example.com',
            password='StrongPass123!',
            user_type='HOUSE_OWNER',
        )
        self.owner_profile, _ = OwnerProfile.objects.get_or_create(
            user=self.owner_user,
            defaults={'company_name': 'Payout Holdings'},
        )
        self.scout = User.objects.create_user(
            username='scout-payout@example.com',
            email='scout-payout@example.com',
            password='StrongPass123!',
            user_type='PROPERTY_SCOUT',
        )
        self.scout_profile = ScoutProfile.objects.create(
            user=self.scout,
            payout_paystack_recipient_code='RCP_test',
        )
        self.property = Property.objects.create(
            owner=self.owner_profile,
            scouted_by=self.scout,
            title='Scouted Apartment',
            description='A test property',
            property_type='APARTMENT',
            furnishing_status='FURNISHED',
            address='123 Main Street',
            city='Nairobi',
            state='Nairobi',
            country='Kenya',
            rental_price=Decimal('15000.00'),
            bedrooms=2,
            bathrooms=1,
        )
        self.payer = User.objects.create_user(
            username='payout-tenant@example.com',
            email='payout-tenant@example.com',
            password='StrongPass123!',
            user_type='TENANT',
        )

    @patch('apps.accounts.views._get_paystack_bank_choices', return_value=([('TEST001', 'Test Bank')], None))
    @patch('apps.payments.services.PaystackService.create_transfer_recipient')
    def test_scout_profile_can_save_payout_recipient(self, mock_create_recipient, mock_banks):
        mock_create_recipient.return_value = {
            'status': True,
            'data': {'recipient_code': 'RCP_created'},
        }
        self.client.force_login(self.scout)

        profile_response = self.client.get(reverse('accounts:profile'), secure=True)
        save_response = self.client.post(
            reverse('accounts:update_scout_payout_account'),
            {
                'bank_code': 'TEST001',
                'account_number': '1234567890',
                'account_name': 'Property Scout',
            },
            secure=True,
        )

        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, 'Scout commissions and payout account')
        self.assertEqual(save_response.status_code, 302)
        self.scout_profile.refresh_from_db()
        self.assertEqual(self.scout_profile.payout_paystack_recipient_code, 'RCP_created')
        self.assertEqual(self.scout_profile.payout_account_number, '1234567890')

    def make_payment(self, platform_fee, building_fee='0.00'):
        return Payment.objects.create(
            payer=self.payer,
            recipient=self.owner_user,
            property=self.property,
            payment_type='RENT',
            amount=Decimal('10000.00'),
            platform_fee=Decimal(platform_fee),
            building_subscription_fee=Decimal(building_fee),
            owner_amount=Decimal('10000.00') - Decimal(platform_fee) - Decimal(building_fee),
            payment_reference=f'REF-{uuid.uuid4().hex}',
            due_date=timezone.now(),
            status='COMPLETED',
        )

    def test_completed_payment_assigns_scout_ten_percent_of_actual_fee(self):
        payment = self.make_payment('500.00')
        commission = ScoutCommission.objects.get(payment=payment)

        self.assertEqual(commission.company_fee, Decimal('500.00'))
        self.assertEqual(commission.commission_amount, Decimal('50.00'))

    def test_completed_zero_fee_payment_creates_no_commission(self):
        payment = self.make_payment('0.00')

        self.assertFalse(ScoutCommission.objects.filter(payment=payment).exists())

    def test_completed_building_fee_payment_assigns_scout_ten_percent(self):
        payment = self.make_payment('0.00', building_fee='500.00')
        commission = ScoutCommission.objects.get(payment=payment)

        self.assertEqual(commission.company_fee, Decimal('500.00'))
        self.assertEqual(commission.commission_amount, Decimal('50.00'))

    @patch('apps.payments.services.PaystackService.initiate_transfer')
    def test_scout_can_request_pending_commission_payout(self, mock_transfer):
        self.scout.verification_status = 'VERIFIED'
        self.scout.save(update_fields=['verification_status'])
        payment = self.make_payment('500.00')
        commission = ScoutCommission.objects.get(payment=payment)
        mock_transfer.return_value = {
            'status': True,
            'data': {'status': 'pending', 'transfer_code': 'TRF_test', 'currency': 'KES'},
        }
        self.client.force_login(self.scout)

        response = self.client.post(reverse('accounts:request_scout_payout'), secure=True)

        self.assertEqual(response.status_code, 302)
        payout = ScoutPayout.objects.get(scout=self.scout)
        commission.refresh_from_db()
        self.assertEqual(payout.amount, Decimal('50.00'))
        self.assertEqual(payout.status, 'PROCESSING')
        self.assertEqual(commission.status, 'APPROVED')
        mock_transfer.assert_called_once()

    @override_settings(PAYSTACK_SECRET_KEY='test-paystack-secret')
    def test_transfer_webhook_requires_valid_signature_and_marks_payout_paid(self):
        payment = self.make_payment('500.00')
        commission = ScoutCommission.objects.get(payment=payment)
        payout = ScoutPayout.objects.create(
            scout=self.scout,
            amount=commission.commission_amount,
            reference='scout-0123456789abcdef0123456789abcdef',
        )
        payout.commissions.add(commission)
        commission.status = 'APPROVED'
        commission.save(update_fields=['status'])
        payload = json.dumps({
            'event': 'transfer.success',
            'data': {'reference': payout.reference},
        }).encode()
        signature = hmac.new(b'test-paystack-secret', payload, hashlib.sha512).hexdigest()

        response = self.client.post(
            reverse('accounts:paystack_transfer_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        payout.refresh_from_db()
        commission.refresh_from_db()
        self.assertEqual(payout.status, 'PAID')
        self.assertEqual(commission.status, 'PAID')
