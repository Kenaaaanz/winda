from django.apps import AppConfig

class PropertiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.properties'
    label = 'properties'
    verbose_name = 'Properties'

    def ready(self):
        import apps.properties.signals