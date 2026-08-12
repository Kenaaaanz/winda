from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('property/<uuid:property_id>/', views.property_analytics, name='property_analytics'),
    path('api/visits/', views.get_visit_data, name='api_visits'),
    path('api/revenue/', views.get_revenue_data, name='api_revenue'),
    path('export/', views.export_analytics, name='export'),
]