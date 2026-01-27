from task_manager.cpu.consumers import CpuMonitorConsumer
from task_manager.memory.consumers import MemoryMonitorConsumer
from task_manager.gpu.consumers import GpuMonitorConsumer
from task_manager.disk.consumers import DiskMonitorConsumer
from task_manager.events.consumers import EventConsumer
from task_manager.bmc.consumers import BmcMonitorConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path(r"^api/task/cpu/ws/?$", CpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/memory/ws/?$", MemoryMonitorConsumer.as_asgi()),
    re_path(r"^api/task/gpu/ws/?$", GpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/disk/ws/?$", DiskMonitorConsumer.as_asgi()),
    re_path(r"^api/task/events/ws/?$", EventConsumer.as_asgi()),
    re_path(r"^api/task/bmc/ws/?$", BmcMonitorConsumer.as_asgi()),
]
