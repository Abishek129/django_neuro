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
from task_manager.routing import websocket_urlpatterns as task_websocket_urlpatterns
from power.routing import websocket_urlpatterns as power_websocket_urlpatterns
from .ws_auth import KeycloakJwtWsMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neuro_backend.settings')

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": KeycloakJwtWsMiddlewareStack(
            AuthMiddlewareStack(
                URLRouter(
                    terminal_websocket_urlpatterns
                    + control_websocket_urlpatterns
                    + task_websocket_urlpatterns
                    + power_websocket_urlpatterns
                )
            )
        ),
    }
)
