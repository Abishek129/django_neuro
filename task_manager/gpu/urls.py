from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="gpu-status"),
    path("history", views.get_history, name="gpu-history"),
    path("breakdown", views.get_breakdown, name="gpu-breakdown"),
    path("processes", views.get_processes, name="gpu-processes"),
]
