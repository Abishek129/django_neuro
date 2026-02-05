from task_manager.cpu.consumers import (
    CpuMonitorConsumer,
    CpuHistoryConsumer,
    CpuBreakdownConsumer,
    CpuProcessesConsumer,
)
from task_manager.memory.consumers import (
    MemoryMonitorConsumer,
    MemoryHistoryConsumer,
    MemoryBreakdownConsumer,
    MemoryProcessesConsumer,
)
from task_manager.gpu.consumers import (
    GpuMonitorConsumer,
    GpuHistoryConsumer,
    GpuBreakdownConsumer,
    GpuProcessesConsumer,
)
from task_manager.disk.consumers import (
    DiskMonitorConsumer,
    DiskHistoryConsumer,
    DiskBreakdownConsumer,
    DiskProcessesConsumer,
)
from task_manager.events.consumers import EventConsumer
from task_manager.bmc.consumers import (
    BmcMonitorConsumer,
    BmcHistoryConsumer,
    BmcBreakdownConsumer,
)
from task_manager.processes.consumers import UnifiedProcessesConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path(r"^api/task/cpu/ws/?$", CpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/cpu/status/ws/?$", CpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/cpu/history/ws/?$", CpuHistoryConsumer.as_asgi()),
    re_path(r"^api/task/cpu/breakdown/ws/?$", CpuBreakdownConsumer.as_asgi()),
    re_path(r"^api/task/cpu/processes/ws/?$", CpuProcessesConsumer.as_asgi()),
    re_path(r"^api/task/memory/ws/?$", MemoryMonitorConsumer.as_asgi()),
    re_path(r"^api/task/memory/status/ws/?$", MemoryMonitorConsumer.as_asgi()),
    re_path(r"^api/task/memory/history/ws/?$", MemoryHistoryConsumer.as_asgi()),
    re_path(r"^api/task/memory/breakdown/ws/?$", MemoryBreakdownConsumer.as_asgi()),
    re_path(r"^api/task/memory/processes/ws/?$", MemoryProcessesConsumer.as_asgi()),
    re_path(r"^api/task/gpu/ws/?$", GpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/gpu/status/ws/?$", GpuMonitorConsumer.as_asgi()),
    re_path(r"^api/task/gpu/history/ws/?$", GpuHistoryConsumer.as_asgi()),
    re_path(r"^api/task/gpu/breakdown/ws/?$", GpuBreakdownConsumer.as_asgi()),
    re_path(r"^api/task/gpu/processes/ws/?$", GpuProcessesConsumer.as_asgi()),
    re_path(r"^api/task/disk/ws/?$", DiskMonitorConsumer.as_asgi()),
    re_path(r"^api/task/disk/status/ws/?$", DiskMonitorConsumer.as_asgi()),
    re_path(r"^api/task/disk/history/ws/?$", DiskHistoryConsumer.as_asgi()),
    re_path(r"^api/task/disk/breakdown/ws/?$", DiskBreakdownConsumer.as_asgi()),
    re_path(r"^api/task/disk/processes/ws/?$", DiskProcessesConsumer.as_asgi()),
    re_path(r"^api/task/events/ws/?$", EventConsumer.as_asgi()),
    re_path(r"^api/task/bmc/ws/?$", BmcMonitorConsumer.as_asgi()),
    re_path(r"^api/task/bmc/status/ws/?$", BmcMonitorConsumer.as_asgi()),
    re_path(r"^api/task/bmc/history/ws/?$", BmcHistoryConsumer.as_asgi()),
    re_path(r"^api/task/bmc/breakdown/ws/?$", BmcBreakdownConsumer.as_asgi()),
    re_path(r"^api/task/processes/ws/?$", UnifiedProcessesConsumer.as_asgi()),
]
