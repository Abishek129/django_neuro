from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="bmc-status"),
    path("history", views.get_history, name="bmc-history"),
    path("sensors", views.get_sensors, name="bmc-sensors"),
    path("sel", views.get_sel, name="bmc-sel"),
]
