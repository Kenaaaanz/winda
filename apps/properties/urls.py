from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    # ==================== PUBLIC VIEWS ====================
    path('', views.property_list, name='list'),
    path('search/autocomplete/', views.property_search_autocomplete, name='search_autocomplete'),
    path('<uuid:pk>/', views.property_detail, name='detail'),
    
    # ==================== OWNER PROPERTY MANAGEMENT ====================
    path('owner/', views.owner_properties, name='owner_properties'),
    path('<uuid:pk>/dashboard/', views.property_dashboard, name='property_dashboard'),
    path('<uuid:pk>/tenants/', views.property_tenants, name='property_tenants'),
    path('<uuid:pk>/payments/', views.property_payments, name='property_payments'),
    path('<uuid:pk>/maintenance/', views.property_maintenance, name='property_maintenance'),
    path('create/', views.property_create, name='create'),
    path('<uuid:pk>/edit/', views.property_edit, name='edit'),
    path('<uuid:pk>/delete/', views.property_delete, name='delete'),
    
    # ==================== IMAGE MANAGEMENT (POST endpoints) ====================
    path('<uuid:pk>/images/manage/', views.property_images_manage, name='images_manage'),
    path('<uuid:pk>/images/upload/', views.upload_property_images, name='upload_images'),
    path('<uuid:pk>/images/set-main/', views.set_main_image, name='set_main_image'),
    path('<uuid:pk>/images/set-thumbnail/', views.set_thumbnail, name='set_thumbnail'),
    path('<uuid:pk>/images/caption/', views.update_image_caption, name='update_caption'),
    path('<uuid:pk>/images/delete/', views.delete_property_image, name='delete_image'),
    path('<uuid:pk>/images/reorder/', views.reorder_images, name='reorder_images'),
    
    # ==================== FAVORITES ====================
    path('<uuid:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/', views.favorites_list, name='favorites'),
    
    # ==================== DOCUMENTS ====================
    path('<uuid:pk>/documents/upload/', views.upload_document, name='upload_document'),
    path('documents/<int:doc_id>/delete/', views.delete_document, name='delete_document'),

    # Unit Management
    path('<uuid:pk>/units/', views.manage_units, name='manage_units'),
    path('<uuid:pk>/units/bulk-add/', views.bulk_add_units, name='bulk_add_units'),
    path('unit/<uuid:unit_id>/toggle/', views.toggle_unit_availability, name='toggle_unit'),
    path('unit/<uuid:unit_id>/delete/', views.delete_unit, name='delete_unit'),
    path('unit/<uuid:unit_id>/', views.unit_detail, name='unit_detail'),
]