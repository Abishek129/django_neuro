from django.urls import include, path

urlpatterns = [
    path("cpu/", include("task_manager.cpu.urls")),
    path("memory/", include("task_manager.memory.urls")),
    path("gpu/", include("task_manager.gpu.urls")),
    path("disk/", include("task_manager.disk.urls")),
    path("events/", include("task_manager.events.urls")),
    path("bmc/", include("task_manager.bmc.urls")),
]
