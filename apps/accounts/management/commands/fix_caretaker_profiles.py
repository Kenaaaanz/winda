from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import CaretakerProfile, OwnerProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Fix missing caretaker profiles for users with CARETAKER type'

    def handle(self, *args, **options):
        self.stdout.write('Checking for caretaker users without profiles...')
        
        # Get all users with CARETAKER type
        caretaker_users = User.objects.filter(user_type='CARETAKER')
        self.stdout.write(f'Found {caretaker_users.count()} caretaker users')
        
        # Get the first owner (or prompt for one)
        owners = OwnerProfile.objects.all()
        if not owners.exists():
            self.stdout.write(self.style.ERROR('No owner found. Please create an owner first.'))
            return
        
        owner = owners.first()
        self.stdout.write(f'Using owner: {owner.company_name}')
        
        fixed_count = 0
        for user in caretaker_users:
            # Check if profile exists
            if not hasattr(user, 'caretaker_profile'):
                self.stdout.write(f'Creating profile for {user.email}...')
                try:
                    profile = CaretakerProfile.objects.create(
                        user=user,
                        owner=owner,
                        permission_level='BASIC',
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created profile for {user.email} (ID: {profile.id})'))
                    fixed_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed to create profile for {user.email}: {e}'))
            else:
                self.stdout.write(f'  ✓ Profile exists for {user.email}')
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} missing profiles'))