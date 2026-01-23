from django.urls import re_path

from .consumers import NotificationConsumer

websocket_urlpatterns = [
    re_path(r"^api/control/notifications/ws/?$", NotificationConsumer.as_asgi()),
]
