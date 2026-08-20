from django.core.management.base import BaseCommand
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Fix caretaker email verification status'

    def handle(self, *args, **options):
        # Find all caretaker users
        caretakers = User.objects.filter(user_type='CARETAKER')
        
        fixed_count = 0
        for user in caretakers:
            if not user.is_email_verified:
                self.stdout.write(f'Fixing {user.email}...')
                user.is_email_verified = True
                user.verification_status = 'VERIFIED'
                user.save()
                fixed_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ {user.email} verified'))
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} caretaker accounts'))