from django.urls import re_path

from .consumers import TerminalConsumer

websocket_urlpatterns = [
    re_path(r"^api/terminal/ws/?$", TerminalConsumer.as_asgi()),
    re_path(r"^api/terminal/ws/(?P<session_id>[0-9a-f-]+)/?$", TerminalConsumer.as_asgi()),
]
