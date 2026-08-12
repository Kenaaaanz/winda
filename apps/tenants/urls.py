from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Tenant Applications (Public)
    path('', views.application_list, name='applications'),
    path('apply/<uuid:property_id>/', views.apply_for_property, name='apply'),
    path('application/<uuid:pk>/', views.application_detail, name='application_detail'),
    path('application/<uuid:pk>/review/', views.application_review, name='application_review'),
    path('application/<uuid:pk>/cancel/', views.cancel_application, name='cancel_application'),
    
    # Leases
    path('leases/', views.lease_list, name='lease_list'),
    path('leases/<uuid:pk>/', views.lease_detail, name='lease_detail'),
    path('leases/create/<uuid:application_id>/', views.lease_create, name='lease_create'),
    path('leases/<uuid:pk>/sign/', views.lease_sign, name='lease_sign'),
    path('leases/<uuid:pk>/terminate/', views.lease_terminate, name='lease_terminate'),
    
    # Owner Tenant Management
    path('owner/tenants/', views.tenant_list, name='tenant_list'),
    path('owner/tenants/pending/', views.pending_tenants, name='pending_tenants'),
    path('owner/tenants/pending/<uuid:pk>/', views.pending_application_detail, name='pending_application_detail'),
    path('owner/tenants/pending/<uuid:pk>/review/', views.review_application, name='review_application'),
    path('owner/tenants/bulk-review/', views.bulk_review_applications, name='bulk_review_applications'),
    path('owner/tenants/<uuid:tenant_id>/', views.tenant_detail, name='tenant_detail'),
    path('owner/tenants/<uuid:tenant_id>/manage/', views.tenant_manage, name='tenant_manage'),
    path('owner/tenants/bulk-action/', views.bulk_tenant_action, name='bulk_tenant_action'),
]