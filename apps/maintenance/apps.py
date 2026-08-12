from django.apps import AppConfig

class MaintenanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.maintenance'
    label = 'maintenance'
    verbose_name = 'Maintenance'

    def ready(self):
        import apps.maintenance.signals