from django.contrib import admin
from django.utils.html import format_html
from .models import Property, PropertyImage, PropertyDocument


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'city', 'rental_price', 'verification_status', 'availability_status')
    list_filter = ('verification_status', 'availability_status', 'property_type', 'city')
    search_fields = ('title', 'address', 'city', 'owner__user__email')
    readonly_fields = ('view_count', 'inquiry_count', 'favorite_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'title', 'description', 'property_type', 'furnishing_status')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 'latitude', 'longitude')
        }),
        ('Pricing', {
            'fields': ('rental_price', 'service_charge', 'security_deposit', 'negotiation_allowed')
        }),
        ('Property Details', {
            'fields': ('bedrooms', 'bathrooms', 'parking_spaces', 'square_feet', 
                      'floor_number', 'total_floors', 'year_built')
        }),
        ('Amenities & Features', {
            'fields': ('amenities', 'features'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('main_image', 'images', 'video_url', 'virtual_tour_url'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('documents',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('verification_status', 'availability_status', 'is_featured', 'is_verified', 'verified_at')
        }),
        ('Analytics', {
            'fields': ('view_count', 'inquiry_count', 'favorite_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on user permissions"""
        if not request.user.is_superuser:
            return self.readonly_fields + ('verification_status', 'is_verified', 'verified_at')
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Handle saving the model"""
        if not change:  # New property
            obj.save()
            # Create initial verification status
            obj.verification_status = 'PENDING'
        super().save_model(request, obj, form, change)


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'image_preview', 'is_main', 'order', 'uploaded_at')
    list_filter = ('is_main', 'property')
    search_fields = ('property__title', 'caption')
    readonly_fields = ('uploaded_at',)
    
    def image_preview(self, obj):
        """Show image preview in admin"""
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit:cover;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Preview'
    
    fieldsets = (
        (None, {
            'fields': ('property', 'image', 'is_main', 'caption', 'order')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('property', 'document_type', 'is_verified', 'uploaded_at')
    list_filter = ('document_type', 'is_verified', 'property')
    search_fields = ('property__title', 'description')
    readonly_fields = ('uploaded_at',)
    
    fieldsets = (
        (None, {
            'fields': ('property', 'document_type', 'document', 'description')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at', 'verified_by')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Handle saving the model"""
        if obj.is_verified and not obj.verified_at:
            from django.utils import timezone
            obj.verified_at = timezone.now()
            obj.verified_by = request.user
        super().save_model(request, obj, form, change)