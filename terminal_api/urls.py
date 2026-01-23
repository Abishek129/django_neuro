from django.urls import path

from . import views

urlpatterns = [
    path("sessions", views.list_sessions, name="terminal-sessions"),
    path("ws", views.websocket_placeholder, name="terminal-ws"),
]
