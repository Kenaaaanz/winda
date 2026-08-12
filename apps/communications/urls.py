from django.urls import path
from . import views

app_name = 'communications'

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('<uuid:room_id>/', views.chat_detail, name='chat_detail'),
    path('<uuid:room_id>/settings/', views.chat_settings, name='chat_settings'),
    path('start/', views.start_chat, name='start_chat'),
    path('start/user/<uuid:user_id>/', views.start_chat, name='start_chat_user'),
    path('start/property/<uuid:property_id>/', views.start_chat, name='start_chat_property'),
    path('message/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('unread/count/', views.get_unread_count, name='unread_count'),
    path('blocked/', views.blocked_users, name='blocked_users'),
    path('recent-chats/', views.recent_chats, name='recent_chats'),
]