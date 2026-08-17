import uuid
import time
from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler

def upload_property_image_to_cloudinary(image_file, property_id, image_type='gallery'):
    """
    Helper function to upload a property image to Cloudinary
    Returns: dict with 'url', 'public_id', 'secure_url' or None
    """
    try:
        # Generate unique ID
        unique_id = f"{image_type}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Compress image
        compressed = CloudinaryImageHandler.compress_image(image_file)
        
        # Upload to Cloudinary
        result = CloudinaryService.upload_property_image(
            compressed,
            str(property_id),
            unique_id
        )
        
        if result:
            public_id = result.get('public_id', '')
            # Truncate if too long
            if len(public_id) > 500:
                public_id = public_id[:500]
            
            return {
                'url': result['secure_url'],
                'public_id': public_id,
                'secure_url': result['secure_url']
            }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
    
    return None