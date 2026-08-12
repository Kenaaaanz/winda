
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Property

User = get_user_model()

class PropertiesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='testpassword123',
            user_type='HOUSE_OWNER'
        )
        self.client.login(username='owner@example.com', password='testpassword123')
        
        self.property_data = {
            'title': 'Test Property',
            'description': 'This is a test property',
            'property_type': 'APARTMENT',
            'furnishing_status': 'UNFURNISHED',
            'address': '123 Test Street',
            'city': 'Nairobi',
            'state': 'Nairobi',
            'rental_price': 50000,
            'bedrooms': 2,
            'bathrooms': 2,
            'parking_spaces': 1,
        }
    
    def test_create_property(self):
        response = self.client.post(reverse('properties:create'), self.property_data, secure=True)
        self.assertEqual(response.status_code, 302)  # Redirect on success
        self.assertTrue(Property.objects.filter(title='Test Property').exists())
