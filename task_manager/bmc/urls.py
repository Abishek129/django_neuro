from django.urls import path

from . import views

urlpatterns = [
    # Core endpoints (match cpu/memory/gpu/disk pattern)
    path("status", views.get_status, name="bmc-status"),
    path("history", views.get_history, name="bmc-history"),
    path("history/clear", views.clear_history, name="bmc-clear-history"),

    # Detailed sensor endpoints
    path("live/", views.live_sensors),
    path("available/", views.available_sensors),

    # PWM fan control
    path("pwm/controls/", views.pwm_controls),
    path("pwm/set-value/", views.pwm_set_value),
    path("pwm/set-mode/", views.pwm_set_mode),

    # IPMI integration
    path("ipmi/status/", views.ipmi_status),
    path("ipmi/sensors/", views.ipmi_sensors),
    path("ipmi/chassis/", views.ipmi_chassis),
    path("ipmi/sel/", views.ipmi_sel),

    # System info
    path("system/info/", views.system_info),
    path("system/power/", views.power_status),

    # Raw sensor data
    path("raw/", views.raw_sensors),
]