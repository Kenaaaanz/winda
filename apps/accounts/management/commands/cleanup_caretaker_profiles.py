from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import User, CaretakerProfile, CaretakerPropertyAssignment
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Clean up duplicate caretaker profiles and fix UUID issues'

    def handle(self, *args, **options):
        self.stdout.write('Cleaning up caretaker profiles...')
        
        # Find all caretaker users
        caretaker_users = User.objects.filter(user_type='CARETAKER')
        
        for user in caretaker_users:
            profiles = CaretakerProfile.objects.filter(user=user)
            count = profiles.count()
            
            if count > 1:
                self.stdout.write(f'Found {count} profiles for {user.email}')
                
                # Keep the first one, delete the rest
                keep = profiles.first()
                to_delete = profiles.exclude(id=keep.id)
                
                for profile in to_delete:
                    self.stdout.write(f'  Deleting profile ID: {profile.id}')
                    # Transfer any assignments
                    assignments = CaretakerPropertyAssignment.objects.filter(caretaker=profile)
                    for assignment in assignments:
                        assignment.caretaker = keep
                        assignment.save()
                    profile.delete()
                
                self.stdout.write(f'  ✓ Kept profile ID: {keep.id}')
            
            elif count == 0:
                self.stdout.write(f'  ✗ No profile found for {user.email}')
            else:
                profile = profiles.first()
                self.stdout.write(f'  ✓ One profile found for {user.email} (ID: {profile.id})')
        
        self.stdout.write(self.style.SUCCESS('Cleanup complete!'))