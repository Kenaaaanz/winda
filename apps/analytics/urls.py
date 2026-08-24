from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard
    path('', views.analytics_dashboard, name='dashboard'),
    path('property/<uuid:property_id>/', views.property_analytics, name='property_analytics'),
    
    # Reports
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/<uuid:report_id>/', views.report_detail, name='report_detail'),
    path('reports/<uuid:report_id>/download/', views.download_report, name='download_report'),
    
    # Export
    path('export/', views.export_data, name='export_data'),
]