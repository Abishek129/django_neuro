from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="power-status"),
    path("authenticate", views.authenticate, name="power-auth"),
    path("sleep", views.sleep, name="power-sleep"),
    path("restart", views.restart, name="power-restart"),
    path("shutdown", views.shutdown, name="power-shutdown"),
]
