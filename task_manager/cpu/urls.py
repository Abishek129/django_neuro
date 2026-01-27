from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="cpu-status"),
    path("history", views.get_history, name="cpu-history"),
    path("breakdown", views.get_breakdown, name="cpu-breakdown"),
    path("processes", views.get_processes, name="cpu-processes"),
]
