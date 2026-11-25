from django.urls import path

from . import views

app_name = 'utilities'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('devices/register/', views.register_device, name='register_device'),
    path(
        'devices/<uuid:device_id>/created/',
        views.device_created,
        name='device_created',
    ),
    path(
        'api/devices/<uuid:device_id>/readings/',
        views.ingest_reading,
        name='ingest_reading',
    ),
]
