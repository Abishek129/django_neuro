import json
import os

import psutil
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
QUEUE_KEY = "memory:usage:history"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_memory_history() -> dict:
    try:
        client = _get_redis_client()
        raw = client.lrange(QUEUE_KEY, 0, -1)
        history = [json.loads(entry) for entry in raw]
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": [], "count": 0}


def _bytes_to_mb(value: int) -> float:
    return round(value / (1024 * 1024), 2)


def _bytes_to_gb(value: int) -> float:
    return round(value / (1024 * 1024 * 1024), 2)


def get_memory_status() -> dict:
    try:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "ram": {
                "total": _bytes_to_gb(vm.total),
                "available": _bytes_to_gb(vm.available),
                "used": _bytes_to_gb(vm.used),
                "percent": vm.percent,
                "total_bytes": vm.total,
                "available_bytes": vm.available,
                "used_bytes": vm.used,
            },
            "swap": {
                "total": _bytes_to_gb(swap.total),
                "used": _bytes_to_gb(swap.used),
                "free": _bytes_to_gb(swap.free),
                "percent": swap.percent,
                "total_bytes": swap.total,
                "used_bytes": swap.used,
                "free_bytes": swap.free,
            },
        }
    except Exception as e:
        return {"error": str(e)}


def _categorize(name: str) -> str:
    if name and name.startswith("job_"):
        return "jobs"
    if name and name.startswith("ai_"):
        return "ai_agents"
    return "apps"


def get_memory_breakdown() -> dict:
    try:
        buckets = {
            "jobs": {"memory_percent": 0.0, "rss_bytes": 0},
            "apps": {"memory_percent": 0.0, "rss_bytes": 0},
            "ai_agents": {"memory_percent": 0.0, "rss_bytes": 0},
        }
        for proc in psutil.process_iter(['name', 'memory_percent', 'memory_info']):
            try:
                info = proc.info
                cat = _categorize(info['name'])
                buckets[cat]["memory_percent"] += info['memory_percent'] or 0.0
                mem_info = info.get('memory_info')
                if mem_info:
                    buckets[cat]["rss_bytes"] += mem_info.rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        for cat in buckets:
            buckets[cat]["memory_percent"] = round(buckets[cat]["memory_percent"], 2)
            buckets[cat]["rss_mb"] = _bytes_to_mb(buckets[cat]["rss_bytes"])

        return buckets
    except Exception as e:
        return {"error": str(e)}


def get_memory_processes(limit: int = 20) -> dict:
    try:
        processes = []
        for proc in psutil.process_iter(
            ['pid', 'name', 'memory_info', 'memory_percent', 'status', 'username']
        ):
            try:
                info = proc.info
                mem_info = info.get('memory_info')
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "rss": _bytes_to_mb(mem_info.rss) if mem_info else 0,
                    "vms": _bytes_to_mb(mem_info.vms) if mem_info else 0,
                    "rss_bytes": mem_info.rss if mem_info else 0,
                    "vms_bytes": mem_info.vms if mem_info else 0,
                    "memory_percent": round(info['memory_percent'] or 0.0, 2),
                    "status": info['status'],
                    "username": info['username'],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        processes.sort(key=lambda p: p["memory_percent"], reverse=True)
        return {
            "processes": processes[:limit],
            "total_count": len(processes),
        }
    except Exception as e:
        return {"error": str(e), "processes": [], "total_count": 0}
