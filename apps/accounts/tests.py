from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

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

