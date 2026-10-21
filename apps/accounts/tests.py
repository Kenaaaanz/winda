from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from apps.analytics.models import AnalyticsEvent
from apps.accounts.forms import ScoutCreationForm
from apps.emails.utils import EmailService
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
