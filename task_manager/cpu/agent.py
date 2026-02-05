import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

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
BMC_QUEUE_KEY = "bmc:usage:history"

# CPU: 1 second interval, 30 minutes of data (1800 entries)
CPU_MAX_QUEUE_LENGTH = 1800
CPU_INTERVAL_SECONDS = 1

# Other metrics: 60 second interval, 30 entries (30 minutes)
MAX_QUEUE_LENGTH = 30
INTERVAL_SECONDS = 60


def get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def collect_cpu_usage() -> dict:
    return {
        "cpu_percent": psutil.cpu_percent(interval=0),
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
        #print(parts, "++++++++++++++++++++")
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
    # Get per-disk counters to exclude sda
    before_disks = psutil.disk_io_counters(perdisk=True)
    time.sleep(1)
    after_disks = psutil.disk_io_counters(perdisk=True)

    # Aggregate all disks except sda
    total_read_before = 0
    total_write_before = 0
    total_read_after = 0
    total_write_after = 0

    for disk_name in before_disks.keys():
        if disk_name.startswith('sda'):
            continue
        if disk_name in after_disks:
            total_read_before += before_disks[disk_name].read_bytes
            total_write_before += before_disks[disk_name].write_bytes
            total_read_after += after_disks[disk_name].read_bytes
            total_write_after += after_disks[disk_name].write_bytes

    read_bytes_per_sec = total_read_after - total_read_before
    write_bytes_per_sec = total_write_after - total_write_before

    return {
        "read_mb_per_sec": round(read_bytes_per_sec / (1024 * 1024), 2),
        "write_mb_per_sec": round(write_bytes_per_sec / (1024 * 1024), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def collect_power_data() -> dict:
    """Collect system power consumption from available sources."""
    power_data = {"total_watts": None, "sources": [], "available": False}

    # Try IPMI power sensors
    try:
        if shutil.which("ipmitool"):
            result = subprocess.run(
                ["ipmitool", "sdr", "elist"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if any(keyword in line.lower() for keyword in ['power', 'watt', 'pwr']):
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 2:
                            try:
                                value_str = parts[1].replace('Watts', '').strip()
                                if value_str and value_str != 'na':
                                    watts = float(value_str)
                                    power_data["sources"].append({
                                        "name": parts[0],
                                        "watts": watts,
                                        "source": "ipmi"
                                    })
                                    if "system" in parts[0].lower() or "total" in parts[0].lower():
                                        power_data["total_watts"] = watts
                                        power_data["available"] = True
                            except (ValueError, IndexError):
                                continue
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    # Try hwmon power sensors
    try:
        for hwmon_path in Path("/sys/class/hwmon").iterdir():
            for power_file in hwmon_path.glob("power*_input"):
                try:
                    with open(power_file) as f:
                        power_uw = int(f.read().strip())
                        power_w = power_uw / 1_000_000
                        label = power_file.name
                        power_data["sources"].append({
                            "name": label,
                            "watts": power_w,
                            "source": "hwmon"
                        })
                        power_data["available"] = True
                except (PermissionError, ValueError, IOError):
                    continue
    except Exception:
        pass

    return power_data


def collect_bmc_usage() -> dict | None:
    """Collect detailed BMC/hardware sensor data from lm-sensors."""
    if not shutil.which("sensors"):
        return None
    try:
        result = subprocess.run(
            ["sensors", "-j"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        raw_data = json.loads(result.stdout)

        # Parse detailed sensor data
        fans = []
        temperatures = []
        voltages = []

        for chip_name, chip_data in raw_data.items():
            adapter = chip_data.get("Adapter", "Unknown")

            for sensor_name, sensor_data in chip_data.items():
                if sensor_name == "Adapter" or not isinstance(sensor_data, dict):
                    continue

                # Process each sensor input
                for key, value in sensor_data.items():
                    if key.endswith("_input"):
                        base_key = key.replace("_input", "")

                        if "fan" in key and isinstance(value, (int, float)):
                            fans.append({
                                "chip": chip_name,
                                "adapter": adapter,
                                "name": base_key,
                                "label": sensor_name,
                                "rpm": value,
                                "alarm": sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                            })
                        elif "temp" in key and isinstance(value, (int, float)):
                            temperatures.append({
                                "chip": chip_name,
                                "adapter": adapter,
                                "name": base_key,
                                "label": sensor_name,
                                "current": value,
                                "max": sensor_data.get(f"{base_key}_max"),
                                "crit": sensor_data.get(f"{base_key}_crit"),
                                "alarm": sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                            })
                        elif "in" in key and isinstance(value, (int, float)):
                            voltages.append({
                                "chip": chip_name,
                                "adapter": adapter,
                                "name": base_key,
                                "label": sensor_name,
                                "voltage": value,
                                "alarm": sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                            })

        if not temperatures and not fans and not voltages:
            return None

        # Include summary stats for backward compatibility and threshold checking
        temp_values = [t["current"] for t in temperatures if t.get("current") is not None]
        fan_rpms = [f["rpm"] for f in fans if f.get("rpm") and f["rpm"] > 0]

        # Collect power data
        power_data = collect_power_data()

        return {
            "fans": fans,
            "temperatures": temperatures,
            "voltages": voltages,
            "power": power_data,
            "summary": {
                "max_temp": round(max(temp_values), 1) if temp_values else None,
                "avg_temp": round(sum(temp_values) / len(temp_values), 1) if temp_values else None,
                "min_fan_rpm": round(min(fan_rpms), 0) if fan_rpms else None,
                "avg_fan_rpm": round(sum(fan_rpms) / len(fan_rpms), 0) if fan_rpms else None,
                "total_watts": power_data.get("total_watts"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def check_thresholds(metric: str, value: float, max_value:float):
    """Check value against thresholds and create Event + notify WebSocket if exceeded."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from task_manager.models import Event

    for severity, threshold in THRESHOLDS.get(metric, []):
        
        if value/max_value * 100 >= threshold:
            
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


def push_to_queue(client: redis.Redis, key: str, data: dict, max_length: int = MAX_QUEUE_LENGTH):
    client.lpush(key, json.dumps(data))
    client.ltrim(key, 0, max_length - 1)


def run():
    logger.info(
        "System usage agent started (CPU: %ds interval, %d entries; Others: %ds interval, %d entries)",
        CPU_INTERVAL_SECONDS, CPU_MAX_QUEUE_LENGTH, INTERVAL_SECONDS, MAX_QUEUE_LENGTH
    )
    client = get_redis_client()
    iteration = 0

    while True:
        try:
            # Collect CPU data every second
            cpu_data = collect_cpu_usage()
            push_to_queue(client, CPU_QUEUE_KEY, cpu_data, max_length=CPU_MAX_QUEUE_LENGTH)
            if iteration % 60 == 0:  # Log every 60 seconds to reduce noise
                logger.info("Recorded CPU usage: %.1f%% at %s", cpu_data["cpu_percent"], cpu_data["timestamp"])
            logger.info("Recorded CPU usage: %.1f%% at %s", cpu_data["cpu_percent"], cpu_data["timestamp"])
            check_thresholds("cpu", cpu_data["cpu_percent"], 100.0)

            # Collect other metrics every 60 seconds
            if iteration % INTERVAL_SECONDS == 0:
                mem_data = collect_memory_usage()
                push_to_queue(client, MEMORY_QUEUE_KEY, mem_data)
                logger.info(
                    "Recorded memory usage: RAM %.1f%% Swap %.1f%% at %s",
                    mem_data["ram_percent"], mem_data["swap_percent"], mem_data["timestamp"],
                )
                check_thresholds("ram", mem_data["ram_percent"], 100.0)
                check_thresholds("swap", mem_data["swap_percent"], 100.0)

                gpu_data = collect_gpu_usage()
                if gpu_data:
                    push_to_queue(client, GPU_QUEUE_KEY, gpu_data)
                    for i, g in enumerate(gpu_data["gpus"]):
                        logger.info(
                            "Recorded GPU %d usage: util %d%% mem_used %.0f MB at %s",
                            i, g["gpu_utilization_percent"], g["memory_used_mb"], gpu_data["timestamp"],
                        )
                        check_thresholds("gpu_util", g["gpu_utilization_percent"], 100.0)
                        check_thresholds("gpu_mem", g["memory_used_mb"], g["memory_total"])

                disk_data = collect_disk_usage()
                push_to_queue(client, DISK_QUEUE_KEY, disk_data)
                logger.info(
                    "Recorded disk I/O: read %.2f MB/s write %.2f MB/s at %s",
                    disk_data["read_mb_per_sec"], disk_data["write_mb_per_sec"], disk_data["timestamp"],
                )
                # Disk threshold checks usage %, not I/O rate
                for part in psutil.disk_partitions(all=False):
                    # Skip virtual/placeholder disks (sda with 0 bytes)
                    if part.device.startswith('/dev/sda'):
                        continue
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        check_thresholds("disk", usage.percent, 100.0)
                    except (PermissionError, OSError):
                        continue

                # Collect BMC/hardware sensor data
                bmc_data = collect_bmc_usage()
                if bmc_data:
                    push_to_queue(client, BMC_QUEUE_KEY, bmc_data)
                    summary = bmc_data.get("summary", {})
                    power_watts = summary.get("total_watts")
                    power_str = f", {power_watts:.0f}W" if power_watts else ""
                    logger.info(
                        "Recorded BMC sensors: %d temps (max %.1f°C), %d fans (avg %d RPM), %d voltages%s at %s",
                        len(bmc_data.get("temperatures", [])),
                        summary.get("max_temp", 0) or 0,
                        len(bmc_data.get("fans", [])),
                        summary.get("avg_fan_rpm", 0) or 0,
                        len(bmc_data.get("voltages", [])),
                        power_str,
                        bmc_data["timestamp"],
                    )
                    # Check temperature thresholds
                    if summary.get("max_temp"):
                        check_thresholds("bmc_temp", summary["max_temp"], 100.0)
                    # Check fan thresholds (low RPM is critical)
                    if summary.get("min_fan_rpm"):
                        # For fans, lower is worse, so invert the logic
                        fan_rpm = summary["min_fan_rpm"]
                        if fan_rpm < 500:  # Critical if any fan below 500 RPM
                            check_thresholds("bmc_fan", 100.0 - (fan_rpm / 10), 100.0)

        except redis.ConnectionError:
            logger.error("Redis connection lost, reconnecting...")
            client = get_redis_client()
        except Exception:
            logger.exception("Error collecting system usage")

        iteration += 1
        time.sleep(CPU_INTERVAL_SECONDS)
