"""
ASGI config for winda project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from apps.communications.consumers import ChatConsumer, NotificationConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'winda.settings')

# Get the ASGI application
django_asgi_app = get_asgi_application()

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/chat/<uuid:room_id>/', ChatConsumer.as_asgi()),
    path('ws/notifications/', NotificationConsumer.as_asgi()),
]

# Application router
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})