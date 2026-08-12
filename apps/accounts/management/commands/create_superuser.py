from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser if none exists'
    
    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            email = input('Email: ')
            password = input('Password: ')
            first_name = input('First name: ')
            last_name = input('Last name: ')
            
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,
                verification_status='VERIFIED'
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser {email} created successfully!'))
        else:
            self.stdout.write(self.style.WARNING('Superuser already exists.'))

