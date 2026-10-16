from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.analytics.models import AnalyticsEvent
from apps.accounts.forms import ScoutCreationForm

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
