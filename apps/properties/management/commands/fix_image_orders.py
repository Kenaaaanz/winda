from django.core.management.base import BaseCommand
from django.db import transaction
from apps.properties.models import PropertyImage

class Command(BaseCommand):
    help = 'Fix duplicate image orders in the database'
    
    def handle(self, *args, **options):
        self.stdout.write('Fixing image orders...')
        
        # Get all properties with images
        from apps.properties.models import Property
        properties = Property.objects.all()
        
        fixed_count = 0
        for property_obj in properties:
            images = property_obj.property_images.filter(is_active=True).order_by('order')
            
            if images.count() > 0:
                # Check for duplicate orders
                orders = list(images.values_list('order', flat=True))
                unique_orders = set(orders)
                
                if len(orders) != len(unique_orders):
                    self.stdout.write(f'Fixing orders for property {property_obj.id}...')
                    
                    with transaction.atomic():
                        # Reassign orders starting from 1
                        for idx, image in enumerate(images, start=1):
                            if image.order != idx:
                                image.order = idx
                                image.save(update_fields=['order'])
                                fixed_count += 1
                    
                    self.stdout.write(f'  ✓ Fixed {fixed_count} images for property {property_obj.id}')
                else:
                    self.stdout.write(f'  ✓ Orders are fine for property {property_obj.id}')
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} images total'))

## **3. Run the Management Command**
