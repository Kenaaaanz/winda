from django.apps import AppConfig

class AdminExtendedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin_extended'
    verbose_name = 'Admin Extended'
    
    def ready(self):
        # Import the admin module to ensure it's loaded
        from . import admin