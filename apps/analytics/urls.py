from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('property/<uuid:property_id>/', views.property_analytics, name='property_analytics'),
    path('api/', views.analytics_api, name='api'),
    path('export/', views.export_analytics, name='export'),
]