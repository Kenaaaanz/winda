from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    path('', views.maintenance_list, name='list'),
    path('create/', views.maintenance_create, name='create'),
    path('<uuid:pk>/', views.maintenance_detail, name='detail'),
    path('<uuid:pk>/assign/', views.maintenance_assign, name='assign'),
    path('<uuid:pk>/add-task/', views.add_task, name='add_task'),
    path('<uuid:pk>/cancel/', views.maintenance_cancel, name='cancel'),
    path('report/', views.maintenance_report, name='report'),
]