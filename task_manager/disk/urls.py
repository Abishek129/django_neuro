from django.urls import path

from . import views

urlpatterns = [
    path("status", views.get_status, name="disk-status"),
    path("history", views.get_history, name="disk-history"),
    path("breakdown", views.get_breakdown, name="disk-breakdown"),
    path("processes", views.get_processes, name="disk-processes"),
]
