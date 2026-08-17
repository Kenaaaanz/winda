import uuid
import time
from apps.common.utils.cloudinary_utils import CloudinaryService, CloudinaryImageHandler

def upload_property_image_to_cloudinary(image_file, property_id, image_type='gallery'):
    """
    Helper function to upload a property image to Cloudinary
    Returns: dict with 'url' (the Cloudinary URL) or None
    """
    try:
        # Generate unique ID
        unique_id = f"{image_type[:3]}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Compress image
        compressed = CloudinaryImageHandler.compress_image(image_file)
        
        # Upload to Cloudinary
        result = CloudinaryService.upload_property_image(
            compressed,
            str(property_id),
            unique_id
        )
        
        if result:
            # Return just the URL
            return {
                'url': result['secure_url'],
            }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
    
    return None