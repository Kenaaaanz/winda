from django.core.management.base import BaseCommand
from apps.properties.models import Property

class Command(BaseCommand):
    help = 'Fix multi-unit properties that were not properly flagged'

    def handle(self, *args, **options):
        self.stdout.write('Checking for properties that should be multi-unit...')
        
        # Find properties with units but is_multi_unit = False
        properties = Property.objects.filter(is_multi_unit=False)
        fixed_count = 0
        
        for prop in properties:
            unit_count = prop.units.count()
            if unit_count > 1:
                self.stdout.write(f'Fixing property {prop.id} - {prop.title} ({unit_count} units)')
                prop.is_multi_unit = True
                prop.total_units = unit_count
                prop.available_units = prop.units.filter(is_available=True).count()
                prop.save()
                fixed_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} properties'))