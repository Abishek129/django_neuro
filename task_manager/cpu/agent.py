import json
import logging
import os
import time
from datetime import datetime, timezone

import shutil
import subprocess

import psutil
import redis

logger = logging.getLogger(__name__)

# Threshold config: metric -> [(severity, threshold)]
THRESHOLDS = {
    "cpu": [
        ("critical", float(os.getenv("CPU_CRIT_THRESHOLD", 95))),
        ("warning", float(os.getenv("CPU_WARN_THRESHOLD", 80))),
    ],
    "ram": [
        ("critical", float(os.getenv("RAM_CRIT_THRESHOLD", 95))),
        ("warning", float(os.getenv("RAM_WARN_THRESHOLD", 80))),
    ],
    "swap": [
        ("critical", float(os.getenv("SWAP_CRIT_THRESHOLD", 90))),
        ("warning", float(os.getenv("SWAP_WARN_THRESHOLD", 70))),
    ],
    "disk": [
        ("critical", float(os.getenv("DISK_CRIT_THRESHOLD", 95))),
        ("warning", float(os.getenv("DISK_WARN_THRESHOLD", 80))),
    ],
    "gpu_util": [
        ("critical", float(os.getenv("GPU_UTIL_CRIT_THRESHOLD", 99))),
        ("warning", float(os.getenv("GPU_UTIL_WARN_THRESHOLD", 90))),
    ],
    "gpu_mem": [
        ("critical", float(os.getenv("GPU_MEM_CRIT_THRESHOLD", 95))),
        ("warning", float(os.getenv("GPU_MEM_WARN_THRESHOLD", 80))),
    ],
    "bmc_temp": [
        ("critical", float(os.getenv("BMC_TEMP_CRIT_THRESHOLD", 85))),
        ("warning", float(os.getenv("BMC_TEMP_WARN_THRESHOLD", 75))),
    ],
    "bmc_fan": [
        ("critical", float(os.getenv("BMC_FAN_CRIT_THRESHOLD", 500))),
        ("warning", float(os.getenv("BMC_FAN_WARN_THRESHOLD", 700))),
    ],
    "bmc_power": [
        ("critical", float(os.getenv("BMC_POWER_CRIT_THRESHOLD", 95))),
        ("warning", float(os.getenv("BMC_POWER_WARN_THRESHOLD", 80))),
    ],
}

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1  # task_manager Redis DB

CPU_QUEUE_KEY = "cpu:usage:history"
MEMORY_QUEUE_KEY = "memory:usage:history"
GPU_QUEUE_KEY = "gpu:usage:history"
DISK_QUEUE_KEY = "disk:usage:history"
MAX_QUEUE_LENGTH = 30
INTERVAL_SECONDS = 60


def get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def collect_cpu_usage() -> dict:
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_memory_usage() -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "ram_percent": vm.percent,
        "swap_percent": swap.percent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_gpu_usage() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,utilization.gpu,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
    except Exception:
        print("efrbjerbgjbwfbjqerjo;bgejbg")
        return None

    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        print(parts, "++++++++++++++++++++")
        if len(parts) >= 2:
            try:
                gpus.append({
                    "memory_used_mb": float(parts[0]),
                    "gpu_utilization_percent": int(parts[1]),
                    "memory_total": float(parts[2]),
                })
            except (ValueError, TypeError):
                continue

    if not gpus:
        return None

    return {
        "gpus": gpus,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_disk_usage() -> dict:
    before = psutil.disk_io_counters()
    time.sleep(1)
    after = psutil.disk_io_counters()
    read_bytes_per_sec = after.read_bytes - before.read_bytes
    write_bytes_per_sec = after.write_bytes - before.write_bytes
    return {
        "read_mb_per_sec": round(read_bytes_per_sec / (1024 * 1024), 2),
        "write_mb_per_sec": round(write_bytes_per_sec / (1024 * 1024), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def check_thresholds(metric: str, value: float, max_value:float):
    """Check value against thresholds and create Event + notify WebSocket if exceeded."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from task_manager.models import Event

    for severity, threshold in THRESHOLDS.get(metric, []):
        
        if value/max_value >= threshold:
            message = f"{metric.upper()} {severity}: {value:.1f}% (threshold {threshold:.0f}%)"
            event = Event.objects.create(
                metric=metric,
                severity=severity,
                message=message,
                value=round(value, 2),
                threshold=threshold,
            )
            logger.warning("Event created: %s", message)

            try:
                channel_layer = get_channel_layer("task_manager")
                async_to_sync(channel_layer.group_send)(
                    "events",
                    {
                        "type": "event_created",
                        "event": {
                            "id": event.id,
                            "metric": event.metric,
                            "severity": event.severity,
                            "message": event.message,
                            "value": event.value,
                            "threshold": event.threshold,
                            "created_at": event.created_at.isoformat(),
                        },
                    },
                )
            except Exception:
                logger.exception("Failed to send event to WebSocket")

            # Only fire the highest matching severity
            break


def push_to_queue(client: redis.Redis, key: str, data: dict):
    client.lpush(key, json.dumps(data))
    client.ltrim(key, 0, MAX_QUEUE_LENGTH - 1)


def run():
    logger.info("System usage agent started (interval=%ds, max_queue=%d)", INTERVAL_SECONDS, MAX_QUEUE_LENGTH)
    client = get_redis_client()

    while True:
        try:
            cpu_data = collect_cpu_usage()
            push_to_queue(client, CPU_QUEUE_KEY, cpu_data)
            logger.info("Recorded CPU usage: %.1f%% at %s", cpu_data["cpu_percent"], cpu_data["timestamp"])
            check_thresholds("cpu", cpu_data["cpu_percent"], 100.0 )

            mem_data = collect_memory_usage()
            push_to_queue(client, MEMORY_QUEUE_KEY, mem_data)
            logger.info(
                "Recorded memory usage: RAM %.1f%% Swap %.1f%% at %s",
                mem_data["ram_percent"], mem_data["swap_percent"], mem_data["timestamp"],
            )
            check_thresholds("ram", mem_data["ram_percent"], 100.0)
            check_thresholds("swap", mem_data["swap_percent"], 100.0)

            gpu_data = collect_gpu_usage()
            #print(gpu_data, "=============")
            if gpu_data:
                push_to_queue(client, GPU_QUEUE_KEY, gpu_data)
                for i, g in enumerate(gpu_data["gpus"]):
                    logger.info(
                        "Recorded GPU %d usage: util %d%% mem_used %.0f MB at %s",
                        i, g["gpu_utilization_percent"], g["memory_used_mb"], gpu_data["timestamp"],
                    )
                    check_thresholds("gpu_util", g["gpu_utilization_percent"], 100.0)
                    #print(g["memory_used_mb"])
                    #print(g)
                    check_thresholds("gpu_mem", g["memory_used_mb"], g["memory_total"])

            disk_data = collect_disk_usage()
            push_to_queue(client, DISK_QUEUE_KEY, disk_data)
            logger.info(
                "Recorded disk I/O: read %.2f MB/s write %.2f MB/s at %s",
                disk_data["read_mb_per_sec"], disk_data["write_mb_per_sec"], disk_data["timestamp"],
            )
            # Disk threshold checks usage %, not I/O rate
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    check_thresholds("disk", usage.percent, 100.0)
                except (PermissionError, OSError):
                    continue
        except redis.ConnectionError:
            logger.error("Redis connection lost, reconnecting...")
            client = get_redis_client()
        except Exception:
            logger.exception("Error collecting system usage")

        time.sleep(INTERVAL_SECONDS)
