import json
import os

import psutil
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
QUEUE_KEY = "disk:usage:history"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def _bytes_to_mb(value: int) -> float:
    return round(value / (1024 * 1024), 2)


def _bytes_to_gb(value: int) -> float:
    return round(value / (1024 * 1024 * 1024), 2)


def get_disk_history() -> dict:
    try:
        client = _get_redis_client()
        raw = client.lrange(QUEUE_KEY, 0, -1)
        history = [json.loads(entry) for entry in raw]
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": [], "count": 0}


def get_disk_status() -> dict:
    try:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            # Skip virtual/placeholder disks (sda with 0 bytes)
            if part.device.startswith('/dev/sda'):
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": _bytes_to_gb(usage.total),
                    "used_gb": _bytes_to_gb(usage.used),
                    "free_gb": _bytes_to_gb(usage.free),
                    "percent": usage.percent,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                })
            except (PermissionError, OSError):
                continue

        # Get per-disk I/O counters, excluding sda
        io_counters = psutil.disk_io_counters(perdisk=True)
        io_stats = None

        # Filter out sda and aggregate remaining disks
        if io_counters:
            total_read_bytes = 0
            total_write_bytes = 0
            total_read_count = 0
            total_write_count = 0

            for disk_name, counters in io_counters.items():
                if disk_name.startswith('sda'):
                    continue
                total_read_bytes += counters.read_bytes
                total_write_bytes += counters.write_bytes
                total_read_count += counters.read_count
                total_write_count += counters.write_count

            io_stats = {
                "read_bytes": total_read_bytes,
                "write_bytes": total_write_bytes,
                "read_count": total_read_count,
                "write_count": total_write_count,
                "read_mb": _bytes_to_mb(total_read_bytes),
                "write_mb": _bytes_to_mb(total_write_bytes),
            }

        return {
            "partitions": partitions,
            "io": io_stats,
        }
    except Exception as e:
        return {"error": str(e)}


def _categorize(name: str) -> str:
    if name and name.startswith("job_"):
        return "jobs"
    if name and name.startswith("ai_"):
        return "ai_agents"
    return "apps"


def get_disk_breakdown() -> dict:
    try:
        buckets = {
            "jobs": {"read_bytes": 0, "write_bytes": 0},
            "apps": {"read_bytes": 0, "write_bytes": 0},
            "ai_agents": {"read_bytes": 0, "write_bytes": 0},
        }
        for proc in psutil.process_iter(['name']):
            try:
                info = proc.info
                io = proc.io_counters()
                cat = _categorize(info['name'])
                buckets[cat]["read_bytes"] += io.read_bytes
                buckets[cat]["write_bytes"] += io.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        for cat in buckets:
            buckets[cat]["read_mb"] = _bytes_to_mb(buckets[cat]["read_bytes"])
            buckets[cat]["write_mb"] = _bytes_to_mb(buckets[cat]["write_bytes"])

        return buckets
    except Exception as e:
        return {"error": str(e)}


def get_disk_processes(limit: int = 20) -> dict:
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'status', 'username']):
            try:
                io = proc.io_counters()
                info = proc.info
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "read_mb": _bytes_to_mb(io.read_bytes),
                    "write_mb": _bytes_to_mb(io.write_bytes),
                    "read_bytes": io.read_bytes,
                    "write_bytes": io.write_bytes,
                    "status": info['status'],
                    "username": info['username'],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        processes.sort(key=lambda p: p["read_bytes"] + p["write_bytes"], reverse=True)
        return {
            "processes": processes[:limit],
            "total_count": len(processes),
        }
    except Exception as e:
        return {"error": str(e), "processes": [], "total_count": 0}
