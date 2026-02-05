from django.urls import re_path

from .consumers import PowerConsumer

websocket_urlpatterns = [
    re_path(r"^api/power/ws/?$", PowerConsumer.as_asgi()),
]
