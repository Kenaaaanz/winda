from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<uuid:pk>/', views.notification_detail, name='detail'),
    path('<uuid:pk>/mark-read/', views.mark_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('<uuid:pk>/archive/', views.archive_notification, name='archive'),
    path('preferences/', views.notification_preferences, name='preferences'),
    path('unread/count/', views.get_unread_count, name='unread_count'),
]