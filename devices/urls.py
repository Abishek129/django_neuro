from django.urls import path

from . import views

urlpatterns = [
    path("", views.get_devices, name="devices"),
    # Bluetooth endpoints disabled for now (no adapter present).
    # path("bluetooth/scan", views.scan_bluetooth, name="devices-bluetooth-scan"),
    # path("bluetooth/connect", views.connect_bluetooth, name="devices-bluetooth-connect"),
    # path("bluetooth/disconnect", views.disconnect_bluetooth, name="devices-bluetooth-disconnect"),
    # path("bluetooth/forget", views.forget_bluetooth, name="devices-bluetooth-forget"),
    path("forget", views.forget_device, name="devices-forget"),
]
