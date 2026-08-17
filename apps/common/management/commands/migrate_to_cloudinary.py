from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import InMemoryUploadedFile
from apps.properties.models import Property, PropertyImage
from apps.accounts.models import User
from apps.common.utils.cloudinary_utils import CloudinaryService
import requests
from io import BytesIO

class Command(BaseCommand):
    help = 'Migrate existing images to Cloudinary'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting migration to Cloudinary...')
        
        # Migrate property main images
        properties = Property.objects.filter(main_image__isnull=False)
        for prop in properties:
            self.stdout.write(f'Migrating property {prop.id} main image...')
            try:
                # Download the image
                response = requests.get(prop.main_image.url)
                if response.status_code == 200:
                    file = BytesIO(response.content)
                    result = CloudinaryService.upload_property_image(
                        file, 
                        str(prop.id), 
                        'main'
                    )
                    if result:
                        prop.main_image = result['secure_url']
                        prop.save()
                        self.stdout.write(f'  ✓ Property {prop.id} main image migrated')
            except Exception as e:
                self.stdout.write(f'  ✗ Failed: {e}')
        
        # Migrate property gallery images
        images = PropertyImage.objects.filter(is_active=True)
        for img in images:
            self.stdout.write(f'Migrating image {img.id}...')
            try:
                response = requests.get(img.image.url)
                if response.status_code == 200:
                    file = BytesIO(response.content)
                    result = CloudinaryService.upload_property_image(
                        file,
                        str(img.property.id),
                        'gallery'
                    )
                    if result:
                        img.image = result['secure_url']
                        img.cloudinary_public_id = result['public_id']
                        img.save()
                        self.stdout.write(f'  ✓ Image {img.id} migrated')
            except Exception as e:
                self.stdout.write(f'  ✗ Failed: {e}')
        
        # Migrate profile pictures
        users = User.objects.filter(profile_picture__isnull=False)
        for user in users:
            self.stdout.write(f'Migrating profile picture for user {user.id}...')
            try:
                response = requests.get(user.profile_picture.url)
                if response.status_code == 200:
                    file = BytesIO(response.content)
                    result = CloudinaryService.upload_profile_picture(file, str(user.id))
                    if result:
                        user.profile_picture = result['secure_url']
                        user.save()
                        self.stdout.write(f'  ✓ User {user.id} profile migrated')
            except Exception as e:
                self.stdout.write(f'  ✗ Failed: {e}')
        
        self.stdout.write(self.style.SUCCESS('Migration complete!'))