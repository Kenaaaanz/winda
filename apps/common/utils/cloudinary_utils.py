import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.conf import settings
from io import BytesIO
from PIL import Image
import base64
import uuid

class CloudinaryService:
    """Service for handling Cloudinary operations"""
    
    @staticmethod
    def upload_image(file, folder='properties', public_id=None, **kwargs):
        """
        Upload an image to Cloudinary
        
        Args:
            file: File object or base64 string
            folder: Folder name in Cloudinary
            public_id: Custom public ID (optional)
            **kwargs: Additional Cloudinary options
        
        Returns:
            dict: Upload response with URL, public_id, etc.
        """
        if not public_id:
            public_id = str(uuid.uuid4())
        
        upload_options = {
            'folder': folder,
            'public_id': public_id,
            'use_filename': True,
            'unique_filename': True,
            'overwrite': True,
        }
        
        # Add transformation options
        if kwargs.get('width') or kwargs.get('height'):
            upload_options['transformation'] = {
                'width': kwargs.get('width', 800),
                'height': kwargs.get('height', 600),
                'crop': kwargs.get('crop', 'limit'),
                'quality': kwargs.get('quality', 'auto'),
                'fetch_format': 'auto'
            }
        
        # Add any additional options
        for key, value in kwargs.items():
            if key not in ['width', 'height', 'crop', 'quality']:
                upload_options[key] = value
        
        try:
            result = cloudinary.uploader.upload(file, **upload_options)
            return result
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            return None
    
    @staticmethod
    def upload_profile_picture(file, user_id):
        """Upload profile picture"""
        folder = f'profiles/{user_id}'
        return CloudinaryService.upload_image(
            file, 
            folder=folder,
            width=400,
            height=400,
            crop='fill',
            quality='auto'
        )
    
    @staticmethod
    def upload_property_image(file, property_id, image_type='main'):
        """Upload property image"""
        folder = f'properties/{property_id}/{image_type}'
        return CloudinaryService.upload_image(
            file,
            folder=folder,
            width=1200,
            height=800,
            crop='limit',
            quality='auto'
        )
    
    @staticmethod
    def upload_property_thumbnail(file, property_id):
        """Upload property thumbnail"""
        folder = f'properties/{property_id}/thumbnails'
        return CloudinaryService.upload_image(
            file,
            folder=folder,
            width=400,
            height=300,
            crop='fill',
            quality='auto'
        )
    
    @staticmethod
    def upload_unit_image(file, property_id, unit_id):
        """Upload unit image"""
        folder = f'properties/{property_id}/units/{unit_id}'
        return CloudinaryService.upload_image(
            file,
            folder=folder,
            width=1200,
            height=800,
            crop='limit',
            quality='auto'
        )
    
    @staticmethod
    def upload_document(file, folder='documents'):
        """Upload document (PDF, etc.)"""
        return CloudinaryService.upload_image(
            file,
            folder=folder,
            resource_type='raw'
        )
    
    @staticmethod
    def delete_image(public_id, resource_type='image'):
        """Delete an image from Cloudinary"""
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
            return None
    
    @staticmethod
    def get_optimized_url(public_id, width=800, height=600, crop='limit'):
        """Get optimized Cloudinary URL"""
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=width,
            height=height,
            crop=crop,
            quality='auto',
            fetch_format='auto'
        )
    
    @staticmethod
    def get_thumbnail_url(public_id, width=300, height=200, crop='fill'):
        """Get thumbnail URL"""
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=width,
            height=height,
            crop=crop,
            quality='auto',
            fetch_format='auto'
        )


class CloudinaryImageHandler:
    """Handler for processing images before upload"""
    
    @staticmethod
    def compress_image(image_file, max_size=(1200, 800), quality=85):
        """Compress image before upload"""
        try:
            img = Image.open(image_file)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            
            # Resize if needed
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            return output
        except Exception as e:
            print(f"Image compression error: {e}")
            return image_file