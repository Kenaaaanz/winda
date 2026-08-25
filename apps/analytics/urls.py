from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main Dashboard
    path('', views.analytics_dashboard, name='dashboard'),
    
    # Property Analytics
    path('property/<uuid:property_id>/', views.property_analytics, name='property_analytics'),
    
    # Trend Views
    path('tenants/', views.tenant_trends, name='tenant_trends'),
    path('payments/', views.payment_trends, name='payment_trends'),
    path('maintenance/', views.maintenance_analytics, name='maintenance_analytics'),
    
    # Custom Reports
    path('custom-report/', views.custom_report, name='custom_report'),
    path('report/<uuid:report_id>/', views.view_report, name='view_report'),
    path('report/<uuid:report_id>/export/', views.export_report, name='export_report'),
    path('report/<uuid:report_id>/schedule/', views.schedule_report, name='schedule_report'),
    
    # API Endpoints
    path('api/', views.analytics_api, name='api'),
    path('api/data/', views.analytics_api, name='api_data'),
    
    # Export
    path('export/', views.export_analytics, name='export'),
]