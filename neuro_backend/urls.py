"""
URL configuration for neuro_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/admin/', admin.site.urls),
    path('api/wifi/', include('wifi.urls')),
    path('api/sound/', include('sound.urls')),
    path('api/devices/', include('devices.urls')),
    path('api/power/', include('power.urls')),
    path('api/terminal/', include('terminal_api.urls')),
    path('api/control/', include('control_pannel.urls')),
    path('api/keycloak/', include('keycloak_api.urls')),
]
