from django.urls import path

from . import views

urlpatterns = [
    path("login", views.login, name="keycloak-login"),
    path("register", views.register, name="keycloak-register"),
    path("authenticate", views.authenticate, name="keycloak-authenticate"),
]
