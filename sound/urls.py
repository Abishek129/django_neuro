from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="sound-status"),
    path("volume", views.volume, name="sound-volume"),
    path("mute", views.mute, name="sound-mute"),
    path("mute/toggle", views.toggle_mute, name="sound-mute-toggle"),
    path("devices", views.get_devices, name="sound-devices"),
    path("device", views.set_device, name="sound-device"),
]
