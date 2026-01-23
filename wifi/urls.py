from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="wifi-status"),
    path("enabled", views.get_enabled, name="wifi-enabled"),
    path("toggle", views.toggle_wifi, name="wifi-toggle"),
    path("networks", views.get_networks, name="wifi-networks"),
    path("current", views.get_current, name="wifi-current"),
    path("connect", views.connect, name="wifi-connect"),
    path("disconnect", views.disconnect, name="wifi-disconnect"),
    path("forget", views.forget, name="wifi-forget"),
]
