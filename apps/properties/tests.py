
from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from PIL import Image
from apps.accounts.models import OwnerProfile
from .models import Property

User = get_user_model()

class PropertiesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='testpassword123',
            user_type='HOUSE_OWNER',
            verification_status='VERIFIED',
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
            'land_reference_number': 'LR-TEST-123',
            'rental_price': 50000,
            'bedrooms': 2,
            'bathrooms': 2,
            'parking_spaces': 1,
        }
    
    def test_create_property(self):
        response = self.client.post(reverse('properties:create'), self.property_data, secure=True)
        self.assertEqual(response.status_code, 302)  # Redirect on success
        self.assertTrue(Property.objects.filter(title='Test Property').exists())

    @patch('apps.common.utils.image_utils.upload_property_image_to_cloudinary')
    def test_scout_can_create_listing_with_uploaded_main_image(self, upload_image):
        scout = User.objects.create_user(
            username='scout@example.com',
            email='scout@example.com',
            password='testpassword123',
            user_type='PROPERTY_SCOUT',
            verification_status='VERIFIED',
        )
        owner_user = User.objects.create_user(
            username='verified-owner@example.com',
            email='verified-owner@example.com',
            password='testpassword123',
            user_type='HOUSE_OWNER',
            verification_status='VERIFIED',
        )
        owner, _ = OwnerProfile.objects.get_or_create(
            user=owner_user,
            defaults={'company_name': 'Verified Owner'},
        )
        upload_image.return_value = {'url': 'https://images.example.com/property.jpg'}
        image_content = BytesIO()
        Image.new('RGB', (1, 1)).save(image_content, format='PNG')
        image = SimpleUploadedFile('property.png', image_content.getvalue(), content_type='image/png')
        self.client.force_login(scout)

        response = self.client.post(
            reverse('properties:create'),
            {
                **self.property_data,
                'property_owner': str(owner.pk),
                'main_image_upload': image,
            },
            secure=True,
        )

        self.assertEqual(
            response.status_code,
            302,
            response.context['form'].errors if response.context else response.status_code,
        )
        property_obj = Property.objects.get(title='Test Property')
        self.assertEqual(property_obj.main_image, 'https://images.example.com/property.jpg')
        self.assertEqual(property_obj.owner, owner)
        self.assertEqual(property_obj.scouted_by, scout)
        upload_image.assert_called_once()
