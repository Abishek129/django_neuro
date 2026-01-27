from django.urls import path

from . import views

urlpatterns = [
    path("live/", views.live_sensors),
    path("available/", views.available_sensors),

    path("pwm/controls/", views.pwm_controls),
    path("pwm/set-value/", views.pwm_set_value),
    path("pwm/set-mode/", views.pwm_set_mode),

    #path("history/", views.history),
    #path("aggregated/", views.aggregated),
    #path("cleanup/", views.cleanup),

    #path("history/intrusion/", views.intrusion_history),
    #path("history/pwm/", views.pwm_history),
    #path("history/alarm/", views.alarm_history),
    #path("history/beep/", views.beep_history),

    path("ipmi/status/", views.ipmi_status),
    path("ipmi/sensors/", views.ipmi_sensors),
    path("ipmi/chassis/", views.ipmi_chassis),
    path("ipmi/sel/", views.ipmi_sel),

    path("system/info/", views.system_info),
    path("system/power/", views.power_status),
]