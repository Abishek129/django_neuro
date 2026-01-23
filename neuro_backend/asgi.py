"""
ASGI config for neuro_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from control_pannel.routing import websocket_urlpatterns as control_websocket_urlpatterns
from terminal_api.routing import websocket_urlpatterns as terminal_websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neuro_backend.settings')

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(terminal_websocket_urlpatterns + control_websocket_urlpatterns)
        ),
    }
)
