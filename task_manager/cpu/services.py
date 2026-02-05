import json
import os

import psutil
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
QUEUE_KEY = "cpu:usage:history"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_cpu_history() -> dict:
    try:
        client = _get_redis_client()
        raw = client.lrange(QUEUE_KEY, 0, -1)
        history = [json.loads(entry) for entry in raw]
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": [], "count": 0}


def get_cpu_status() -> dict:
    try:
        freq = psutil.cpu_freq()
        temps = {}
        try:
            sensor_temps = psutil.sensors_temperatures()
            for chip_name in ("coretemp", "k10temp"):
                if chip_name in sensor_temps:
                    readings = sensor_temps[chip_name]
                    if readings:
                        temps = {
                            "current": readings[0].current,
                            "high": readings[0].high,
                            "critical": readings[0].critical,
                        }
                    break
            if not temps and sensor_temps:
                first_key = next(iter(sensor_temps))
                readings = sensor_temps[first_key]
                if readings:
                    temps = {
                        "current": readings[0].current,
                        "high": readings[0].high,
                        "critical": readings[0].critical,
                    }
        except (AttributeError, StopIteration):
            pass

        times = psutil.cpu_times_percent(interval=0)
        return {
            "cpu_percent_overall": psutil.cpu_percent(interval=1),
            "cpu_percent_per_core": psutil.cpu_percent(interval=0, percpu=True),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "frequency": {
                "current": freq.current if freq else None,
                "min": freq.min if freq else None,
                "max": freq.max if freq else None,
            },
            "temperature": temps if temps else None,
            "breakdown": {
                "user": times.user,
                "system": times.system,
                "idle": times.idle,
                "iowait": getattr(times, "iowait", None),
                "nice": getattr(times, "nice", None),
                "irq": getattr(times, "irq", None),
                "softirq": getattr(times, "softirq", None),
                "steal": getattr(times, "steal", None),
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


def get_cpu_breakdown() -> dict:
    try:
        cpu_count = psutil.cpu_count(logical=True) or 1
        buckets = {
            "jobs": {"cpu_percent": 0.0},
            "apps": {"cpu_percent": 0.0},
            "ai_agents": {"cpu_percent": 0.0},
        }
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            try:
                info = proc.info
                cat = _categorize(info['name'])
                # Normalize by CPU count: psutil returns per-core percentage
                # On a 4-core system, a process using all cores shows as 400%
                # We divide by cpu_count to get percentage of total system CPU
                buckets[cat]["cpu_percent"] += (info['cpu_percent'] or 0.0) / cpu_count
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        for cat in buckets:
            buckets[cat]["cpu_percent"] = round(buckets[cat]["cpu_percent"], 2)

        return buckets
    except Exception as e:
        return {"error": str(e)}


def get_cpu_processes(limit: int = 20) -> dict:
    try:
        cpu_count = psutil.cpu_count(logical=True) or 1
        processes = []
        for proc in psutil.process_iter(
            ['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'username', 'ppid']
        ):
            try:
                info = proc.info
                children = proc.children(recursive=False)
                processes.append({
                    "pid": info['pid'],
                    "ppid": info['ppid'],
                    "name": info['name'],
                    "cpu_percent": round((info['cpu_percent'] or 0.0) / cpu_count, 2),
                    "memory_percent": round(info['memory_percent'] or 0.0, 2),
                    "status": info['status'],
                    "username": info['username'],
                    "children": [{"pid": c.pid, "name": c.name()} for c in children],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
        return {
            "processes": processes[:limit],
            "total_count": len(processes),
        }
    except Exception as e:
        return {"error": str(e), "processes": [], "total_count": 0}
