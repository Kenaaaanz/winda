from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import os

User = get_user_model()

class Property(models.Model):
    PROPERTY_TYPES = (
        ('APARTMENT', 'Apartment'),
        ('BUNGALOW', 'Bungalow'),
        ('MAISONETTE', 'Maisonette'),
        ('DUPLEX', 'Duplex'),
        ('PENTHOUSE', 'Penthouse'),
        ('STUDIO', 'Studio'),
        ('TOWNHOUSE', 'Townhouse'),
        ('COMMERCIAL', 'Commercial'),
        ('LAND', 'Land'),
    )
    
    FURNISHING_STATUS = (
        ('FURNISHED', 'Furnished'),
        ('SEMI_FURNISHED', 'Semi-Furnished'),
        ('UNFURNISHED', 'Unfurnished'),
    )
    
    VERIFICATION_STATUS = (
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('IN_REVIEW', 'In Review'),
    )
    
    AVAILABILITY_STATUS = (
        ('AVAILABLE', 'Available'),
        ('RENTED', 'Rented'),
        ('UNDER_MAINTENANCE', 'Under Maintenance'),
        ('BOOKED', 'Booked'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('accounts.OwnerProfile', on_delete=models.CASCADE, related_name='properties')
    
    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    furnishing_status = models.CharField(max_length=20, choices=FURNISHING_STATUS, default='UNFURNISHED')
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Kenya')
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Pricing - Make these nullable for multi-unit
    rental_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    negotiation_allowed = models.BooleanField(default=False)
    
    # Property Details - Make these nullable for multi-unit
    bedrooms = models.PositiveIntegerField(null=True, blank=True)
    bathrooms = models.PositiveIntegerField(null=True, blank=True)
    parking_spaces = models.PositiveIntegerField(default=0)
    square_feet = models.PositiveIntegerField(null=True, blank=True)
    floor_number = models.PositiveIntegerField(null=True, blank=True)
    total_floors = models.PositiveIntegerField(null=True, blank=True)
    year_built = models.PositiveIntegerField(null=True, blank=True)
    
    # Multi-unit support
    is_multi_unit = models.BooleanField(default=False, help_text='Does this property have multiple units?')
    total_units = models.PositiveIntegerField(default=1, help_text='Total number of units')
    available_units = models.PositiveIntegerField(default=1, help_text='Number of available units')
    
    # Amenities
    amenities = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)
    
    # Media - Store Cloudinary URLs directly (ONLY ONE VERSION)
    main_image = models.URLField(max_length=500, blank=True, null=True)
    thumbnail = models.URLField(max_length=500, blank=True, null=True)
    images = models.JSONField(default=list, blank=True)
    video_url = models.URLField(blank=True, null=True)
    virtual_tour_url = models.URLField(blank=True, null=True)
    
    # Documents
    documents = models.JSONField(default=list, blank=True)
    
    # Status
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_STATUS, default='AVAILABLE')
    is_featured = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Views & Analytics
    view_count = models.PositiveIntegerField(default=0)
    inquiry_count = models.PositiveIntegerField(default=0)
    favorite_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['city', 'property_type']),
            models.Index(fields=['availability_status', 'verification_status']),
            models.Index(fields=['rental_price']),
            models.Index(fields=['bedrooms', 'bathrooms']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.city}"

    @property
    def is_market_available(self):
        """Check if property is available for listing"""
        if self.verification_status != 'VERIFIED':
            return False
        
        if self.is_multi_unit:
            return self.units.filter(is_available=True).exists()
        else:
            return self.availability_status == 'AVAILABLE'
    
    def get_total_price(self):
        """Get total price including service charge"""
        if self.rental_price and self.service_charge:
            return self.rental_price + self.service_charge
        return self.rental_price or 0
    
    def get_main_image_url(self):
        """Get main image URL"""
        return self.main_image if self.main_image else None
    
    def get_thumbnail_url(self):
        """Get thumbnail URL"""
        if self.thumbnail:
            return self.thumbnail
        elif self.main_image:
            return self.main_image
        return None
    
    def get_all_images(self):
        """Get all property images including main and gallery"""
        images = []
        
        if self.main_image:
            images.append({
                'url': self.main_image,
                'thumbnail': self.main_image,
                'is_main': True,
            })
        
        # Get gallery images
        gallery_images = self.property_images.filter(is_active=True).order_by('order')
        for img in gallery_images:
            images.append({
                'url': img.image_url,
                'thumbnail': img.image_url,
                'id': str(img.id),
                'is_main': img.is_main,
                'caption': img.caption,
                'order': img.order,
            })
        
        return images

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('properties:detail', kwargs={'pk': self.id})
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def set_thumbnail(self, image_id):
        """Set a specific image as the thumbnail"""
        try:
            if image_id == 'main':
                if self.main_image:
                    self.thumbnail = self.main_image
                    self.save(update_fields=['thumbnail'])
                    return True
            else:
                image = self.property_images.get(id=image_id)
                if image:
                    self.thumbnail = image.image_url
                    self.save(update_fields=['thumbnail'])
                    return True
        except:
            pass
        return False
    
    def get_available_units_count(self):
        """Get count of available units"""
        if self.is_multi_unit:
            return self.units.filter(is_available=True).count()
        return 1 if self.availability_status == 'AVAILABLE' else 0
    
    def get_total_units_count(self):
        """Get total units count"""
        if self.is_multi_unit:
            return self.units.count()
        return 1

    def get_price_range(self):
        """Get price range for multi-unit properties"""
        if self.is_multi_unit:
            units = self.units.all()
            if units.exists():
                prices = [unit.get_rental_price() for unit in units]
                if len(set(prices)) == 1:
                    return f"KES {prices[0]:,.0f}"
                return f"KES {min(prices):,.0f} - {max(prices):,.0f}"
        elif self.rental_price:
            return f"KES {self.rental_price:,.0f}"
        return "Price not set"

    def get_security_deposit_range(self):
        """Get security deposit range for multi-unit properties"""
        if self.is_multi_unit:
            units = self.units.all()
            if units.exists():
                deposits = [unit.get_security_deposit() for unit in units]
                if len(set(deposits)) == 1:
                    return f"KES {deposits[0]:,.0f}"
                return f"KES {min(deposits):,.0f} - {max(deposits):,.0f}"
        elif self.security_deposit:
            return f"KES {self.security_deposit:,.0f}"
        return "KES 0"
    
    def get_service_charge_range(self):
        """Get service charge range for multi-unit properties"""
        if self.is_multi_unit:
            units = self.units.all()
            if units.exists():
                charges = [unit.get_service_charge() for unit in units]
                if len(set(charges)) == 1:
                    return f"KES {charges[0]:,.0f}"
                return f"KES {min(charges):,.0f} - {max(charges):,.0f}"
        elif self.service_charge:
            return f"KES {self.service_charge:,.0f}"
        return "KES 0"

    
    def get_unit_count_display(self):
        """Get unit count display"""
        if self.is_multi_unit:
            count = self.units.count()
            available = self.units.filter(is_available=True).count()
            return f"{count} units • {available} available"
        return "Single unit"
    
    def get_unit_summary(self):
        """Get summary of units for display"""
        if self.is_multi_unit:
            units = self.units.all()
            if units.exists():
                unit_types = {}
                for unit in units:
                    key = f"{unit.bedrooms}br/{unit.bathrooms}ba"
                    unit_types[key] = unit_types.get(key, 0) + 1
                
                summary_parts = []
                for key, count in unit_types.items():
                    summary_parts.append(f"{count}x {key}")
                
                return ", ".join(summary_parts)
        return None
    
    def refresh_availability_status(self):
        """Refresh availability status based on units or current state"""
        if self.is_multi_unit:
            available_units = self.units.filter(is_available=True).count()
            total_units = self.units.count()
            rented_units = self.units.filter(status='RENTED').count()
            booked_units = self.units.filter(status='BOOKED').count()
            
            self.available_units = available_units
            self.total_units = total_units
            
            if total_units == 0:
                self.availability_status = 'UNDER_MAINTENANCE'
            elif available_units > 0:
                self.availability_status = 'AVAILABLE'
            elif rented_units == total_units:
                self.availability_status = 'RENTED'
            elif booked_units == total_units:
                self.availability_status = 'BOOKED'
            else:
                self.availability_status = 'AVAILABLE'
            
            self.save(update_fields=['availability_status', 'available_units', 'total_units'])
        else:
            # For single unit, just update available units count
            self.available_units = 1 if self.availability_status == 'AVAILABLE' else 0
            self.total_units = 1
            self.save(update_fields=['available_units', 'total_units'])
        
        return self.availability_status
    
    def update_availability_from_units(self):
        """Update availability based on unit status (alias for refresh_availability_status)"""
        return self.refresh_availability_status()


class Unit(models.Model):
    """Individual units within a property (for apartments/buildings)"""
    
    UNIT_STATUS = (
        ('AVAILABLE', 'Available'),
        ('RENTED', 'Rented'),
        ('BOOKED', 'Booked'),
        ('UNDER_MAINTENANCE', 'Under Maintenance'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property_obj = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    
    # Unit identification
    unit_number = models.CharField(max_length=50, help_text='e.g., A1, B2, 101, 202')
    floor_number = models.PositiveIntegerField(null=True, blank=True)
    
    # Unit specifications
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.PositiveIntegerField()
    square_feet = models.PositiveIntegerField(null=True, blank=True)
    
    # Pricing (can override property pricing)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Features and amenities
    amenities = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=UNIT_STATUS, default='AVAILABLE')
    is_available = models.BooleanField(default=True)
    
    # Images
    images = models.JSONField(default=list, blank=True)
    
    # Current tenant
    current_tenant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rented_units')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'property_units'
        ordering = ['unit_number']
        unique_together = ['property_obj', 'unit_number']
    
    def __str__(self):
        return f"{self.property_obj.title} - Unit {self.unit_number}"
    
    @property
    def display_name(self):
        return f"Unit {self.unit_number}"
    
    def get_rental_price(self):
        """Get rental price (unit-specific or fallback to property)"""
        return self.rental_price or self.property_obj.rental_price or 0
    
    def get_service_charge(self):
        """Get service charge (unit-specific or fallback to property)"""
        return self.service_charge or self.property_obj.service_charge or 0
    
    def get_security_deposit(self):
        """Get security deposit (unit-specific or fallback to property)"""
        return self.security_deposit or self.property_obj.security_deposit or 0
    
    def toggle_availability(self):
        """Toggle unit availability"""
        self.is_available = not self.is_available
        self.status = 'AVAILABLE' if self.is_available else 'RENTED'
        self.save()


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_images')
    image_url = models.URLField(max_length=500, blank=True, null=True)
    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_images'
        ordering = ['order']
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    def get_optimized_url(self):
        """Get optimized image URL"""
        return self.image_url if self.image_url else None
    
    def get_thumbnail_url(self):
        """Get thumbnail URL"""
        return self.image_url if self.image_url else None
    
    def delete(self, *args, **kwargs):
        """Delete image from Cloudinary when record is deleted"""
        if self.image_url:
            try:
                from apps.common.utils.cloudinary_utils import CloudinaryService
                # Extract public_id from URL
                parts = self.image_url.split('/')
                for i, part in enumerate(parts):
                    if part == 'upload':
                        if i + 1 < len(parts) and parts[i+1].startswith('v'):
                            public_id_parts = parts[i+2:]
                        else:
                            public_id_parts = parts[i+1:]
                        public_id = '/'.join(public_id_parts).split('.')[0]
                        CloudinaryService.delete_image(public_id)
                        break
            except Exception as e:
                print(f"Error deleting from Cloudinary: {e}")
        super().delete(*args, **kwargs)


class PropertyDocument(models.Model):
    DOCUMENT_TYPES = (
        ('TITLE_DEED', 'Title Deed'),
        ('RENTAL_AGREEMENT', 'Rental Agreement'),
        ('SURVEY_PLAN', 'Survey Plan'),
        ('RATES', 'Rates Payment'),
        ('UTILITY_BILL', 'Utility Bill'),
        ('INSURANCE', 'Insurance'),
        ('OTHER', 'Other'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to='properties/documents/')
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'property_documents'
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.property.title}"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'favorites'
        unique_together = ['user', 'property']
    
    def __str__(self):
        return f"{self.user.email} - {self.property.title}"