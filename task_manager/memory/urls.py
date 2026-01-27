from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="memory-status"),
    path("history", views.get_history, name="memory-history"),
    path("breakdown", views.get_breakdown, name="memory-breakdown"),
    path("processes", views.get_processes, name="memory-processes"),
]
