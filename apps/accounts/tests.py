from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from apps.analytics.models import AnalyticsEvent
from apps.accounts.forms import ScoutCreationForm
from apps.accounts.forms import SocialSignupForm
from apps.emails.utils import EmailService
from apps.payments.models import Payment, ScoutCommission, ScoutPayout
from apps.properties.models import Property
from unittest.mock import patch

User = get_user_model()

class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '+254712345678',
            'user_type': 'TENANT'
        }
    
    def test_user_registration(self):
        response = self.client.post(reverse('accounts:register'), self.user_data)
        self.assertEqual(response.status_code, 302)  # Redirect after registration
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
    
    def test_user_login(self):
        # Create user
        user = User.objects.create_user(**self.user_data)
        user.is_active = True
        user.save()
        
        # Test login
        response = self.client.post(reverse('accounts:login'), {
            'username': 'test@example.com',
            'password': 'testpassword123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login

    def test_property_scout_can_log_in_with_email(self):
        form = ScoutCreationForm(data={
            'email': 'scout@example.com',
            'first_name': 'Property',
            'last_name': 'Scout',
            'phone': '+254712345679',
            'password1': 'scoutpassword123',
            'password2': 'scoutpassword123',
        })
        self.assertTrue(form.is_valid(), form.errors)
        scout = form.save()

        response = self.client.post(reverse('accounts:login'), {
            'username': 'SCOUT@example.com',
            'password': 'scoutpassword123',
        }, secure=True)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('accounts:scout_pending'))
        self.assertEqual(self.client.session['_auth_user_id'], str(scout.pk))

    def test_authenticated_user_pages_use_the_dashboard_sidebar(self):
        tenant = User.objects.create_user(
            username='tenant@example.com',
            email='tenant@example.com',
            password='tenantpassword123',
            user_type='TENANT',
        )
        self.client.force_login(tenant)

        response = self.client.get(reverse('accounts:profile'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dashboard-shell')
        self.assertContains(response, 'dashboard-sidebar')
        self.assertContains(response, 'Find Properties')

    @override_settings(SOCIALACCOUNT_PROVIDERS={
        'google': {'APPS': [{'client_id': 'google-test', 'secret': 'google-secret'}]},
        'apple': {'APPS': [{'client_id': 'apple-test', 'secret': 'apple-secret'}]},
    })
    def test_login_displays_only_configured_social_sso_providers(self):
        response = self.client.get(reverse('accounts:login'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('google_login'))
        self.assertContains(response, reverse('apple_login'))
        self.assertNotContains(response, reverse('microsoft_login'))

    @override_settings(SOCIALACCOUNT_PROVIDERS={
        'google': {'APPS': [{
            'client_id': 'google-test-client',
            'secret': 'google-test-secret',
        }]},
    })
    def test_google_sso_route_starts_provider_authorization(self):
        confirmation = self.client.get(
            reverse('google_login'),
            {'process': 'login'},
            secure=True,
        )
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, 'Sign In Via Google')

        response = self.client.post(
            reverse('google_login'),
            {'process': 'login'},
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('https://accounts.google.com/'))

    @override_settings(SOCIALACCOUNT_PROVIDERS={
        'apple': {'APPS': [{
            'client_id': 'apple-test-client',
            'secret': 'apple-key-id',
            'key': 'apple-team-id',
            'certificate_key': 'test-private-key',
        }]},
        'microsoft': {'APPS': [{
            'client_id': 'microsoft-test-client',
            'secret': 'microsoft-test-secret',
            'settings': {'tenant': 'common'},
        }]},
    })
    def test_apple_and_microsoft_sso_routes_start_authorization(self):
        providers = (
            ('apple', 'https://appleid.apple.com/auth/authorize'),
            ('microsoft', 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'),
        )
        for provider, authorization_url in providers:
            with self.subTest(provider=provider):
                response = self.client.post(
                    reverse(f'{provider}_login'),
                    {'process': 'login'},
                    secure=True,
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith(authorization_url))

    def test_social_signup_requires_a_safe_platform_role(self):
        sociallogin = type('SocialLoginStub', (), {
            'user': User(email='social@example.com'),
        })()
        form = SocialSignupForm(sociallogin=sociallogin)

        self.assertEqual(
            form.fields['user_type'].choices,
            [('TENANT', 'Tenant'), ('HOUSE_OWNER', 'Property owner')],
        )
        self.assertNotIn('SUPER_ADMIN', [choice[0] for choice in form.fields['user_type'].choices])

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        SITE_URL='https://www.winda.africa',
    )
    def test_user_guide_email_contains_role_specific_instructions(self):
        scout = User.objects.create_user(
            username='scout@example.com',
            email='scout@example.com',
            password='scoutpassword123',
            user_type='PROPERTY_SCOUT',
        )

        self.assertTrue(EmailService.send_user_guide_email(scout))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Winda Property Scout guide', mail.outbox[0].subject)
        self.assertIn('Submit Listing', mail.outbox[0].alternatives[0][0])
        self.assertIn('https://www.winda.africa/accounts/login/', mail.outbox[0].alternatives[0][0])

    @patch('apps.accounts.views.EmailService.send_user_guide_email')
    def test_approving_owner_sends_the_user_guide(self, send_user_guide):
        admin = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='adminpassword123',
        )
        owner = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='ownerpassword123',
            user_type='HOUSE_OWNER',
            verification_status='PENDING',
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('accounts:admin_verify_owners'),
            {'user_id': str(owner.pk), 'action': 'approve'},
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        send_user_guide.assert_called_once_with(owner, account_status='approved')

    @patch('apps.accounts.views.EmailService.send_email', return_value=True)
    def test_rejecting_owner_erases_the_account(self, send_rejection_email):
        admin = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='adminpassword123',
        )
        owner = User.objects.create_user(
            username='rejected-owner@example.com',
            email='rejected-owner@example.com',
            password='ownerpassword123',
            first_name='Rejected',
            last_name='Owner',
            user_type='HOUSE_OWNER',
            verification_status='PENDING',
        )
        owner_id = owner.pk
        scout = User.objects.create_user(
            username='scout@example.com',
            email='scout@example.com',
            password='scoutpassword123',
            user_type='PROPERTY_SCOUT',
        )
        property_obj = Property.objects.create(
            owner=owner.owner_profile,
            title='Rejected owner property',
            description='Property linked to a commission',
            property_type='APARTMENT',
            furnishing_status='UNFURNISHED',
            address='1 Test Road',
            city='Nairobi',
            state='Nairobi',
        )
        payment = Payment.objects.create(
            payer=admin,
            recipient=owner,
            property=property_obj,
            payment_type='RENT',
            amount='1000.00',
            payment_reference='owner-rejection-payment',
            due_date=timezone.now(),
        )
        commission = ScoutCommission.objects.create(
            scout=scout,
            property=property_obj,
            payment=payment,
            company_fee='100.00',
            commission_rate='10.00',
            commission_amount='10.00',
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('accounts:admin_verify_owners'),
            {
                'user_id': str(owner_id),
                'action': 'reject',
                'notes': 'Application could not be verified.',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=owner_id).exists())
        self.assertFalse(AnalyticsEvent.objects.filter(user_id=owner_id).exists())
        commission.refresh_from_db()
        self.assertIsNone(commission.property)
        self.assertIsNone(commission.payment)
        send_rejection_email.assert_called_once()

    @patch('apps.accounts.views.EmailService.send_email', return_value=True)
    def test_rejecting_scout_erases_identity_and_redacts_payout(self, send_rejection_email):
        admin = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='adminpassword123',
        )
        scout = User.objects.create_user(
            username='rejected-scout@example.com',
            email='rejected-scout@example.com',
            password='scoutpassword123',
            user_type='PROPERTY_SCOUT',
            verification_status='PENDING',
        )
        scout_id = scout.pk
        payout = ScoutPayout.objects.create(
            scout=scout,
            amount='100.00',
            reference='scout-payout-reference',
            transfer_code='transfer-code',
            paystack_response={'account_name': 'Rejected Scout'},
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('accounts:admin_verify_scouts'),
            {
                'user_id': str(scout_id),
                'action': 'reject',
                'notes': 'Application could not be verified.',
            },
            secure=True,
        )

        payout.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=scout_id).exists())
        self.assertIsNone(payout.scout)
        self.assertEqual(payout.paystack_response, {})
        self.assertEqual(payout.transfer_code, '')
        send_rejection_email.assert_called_once()

    def test_admin_can_create_multiple_property_scouts(self):
        admin = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='adminpassword123',
        )
        self.client.force_login(admin)
        AnalyticsEvent.objects.create(user=admin, event_type='USER_LOGIN')

        dashboard = self.client.get(reverse('admin:index'), secure=True)
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Platform overview')
        self.assertContains(dashboard, 'Platform activity')
        self.assertContains(dashboard, 'User Login')
        self.assertContains(dashboard, reverse('admin:accounts_user_changelist'))
        self.assertContains(dashboard, 'Scout Commissions')
        self.assertContains(dashboard, reverse('admin:payments_scoutcommission_changelist'))
        self.assertContains(dashboard, 'Scout Payouts')
        self.assertContains(dashboard, reverse('admin:payments_scoutpayout_changelist'))

        for email in ('first.scout@example.com', 'second.scout@example.com'):
            response = self.client.post(reverse('admin:accounts_user_add'), {
                'email': email,
                'first_name': 'Property',
                'last_name': 'Scout',
                'phone': '+254712345678',
                'user_type': 'PROPERTY_SCOUT',
                'password1': 'scoutpassword123',
                'password2': 'scoutpassword123',
            }, secure=True)

            self.assertEqual(response.status_code, 302, response.content.decode())
            scout = User.objects.get(email=email)
            self.assertEqual(scout.username, email)
            self.assertEqual(scout.user_type, 'PROPERTY_SCOUT')
            self.assertTrue(scout.check_password('scoutpassword123'))
