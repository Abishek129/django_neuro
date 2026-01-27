import json
import os
import subprocess
import shutil

import psutil
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
QUEUE_KEY = "gpu:usage:history"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_gpu_history() -> dict:
    try:
        client = _get_redis_client()
        raw = client.lrange(QUEUE_KEY, 0, -1)
        history = [json.loads(entry) for entry in raw]
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": [], "count": 0}


def _nvidia_smi_available() -> bool:
    return shutil.which("nvidia-smi") is not None


def _run_nvidia_smi(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["nvidia-smi"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except FileNotFoundError:
        return False, "nvidia-smi not found"
    except subprocess.TimeoutExpired:
        return False, "nvidia-smi timed out"
    except Exception as e:
        return False, str(e)


def _safe_float(val, default=None):
    try:
        return float(val) if val and val != "[N/A]" else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=None):
    try:
        return int(val) if val and val != "[N/A]" else default
    except (ValueError, TypeError):
        return default


def get_gpu_status() -> dict:
    if not _nvidia_smi_available():
        return {
            "available": False,
            "error": "nvidia-smi not found. NVIDIA GPU may not be installed.",
            "gpus": [],
        }

    success, output = _run_nvidia_smi([
        "--query-gpu=index,name,driver_version,memory.total,memory.used,"
        "memory.free,temperature.gpu,utilization.gpu,utilization.memory,"
        "fan.speed,power.draw,power.limit",
        "--format=csv,noheader,nounits",
    ])

    if not success:
        return {
            "available": False,
            "error": output,
            "gpus": [],
        }

    gpus = []
    for line in output.split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 8:
            gpus.append({
                "index": _safe_int(parts[0], 0),
                "name": parts[1] if len(parts) > 1 else "Unknown",
                "driver_version": parts[2] if len(parts) > 2 else "Unknown",
                "memory_total_mb": _safe_float(parts[3]),
                "memory_used_mb": _safe_float(parts[4]),
                "memory_free_mb": _safe_float(parts[5]),
                "temperature_c": _safe_int(parts[6]),
                "gpu_utilization_percent": _safe_int(parts[7]),
                "memory_utilization_percent": _safe_int(parts[8]) if len(parts) > 8 else None,
                "fan_speed_percent": _safe_int(parts[9]) if len(parts) > 9 else None,
                "power_draw_w": _safe_float(parts[10]) if len(parts) > 10 else None,
                "power_limit_w": _safe_float(parts[11]) if len(parts) > 11 else None,
            })

    return {
        "available": True,
        "gpu_count": len(gpus),
        "gpus": gpus,
    }


def _get_per_process_gpu_utilization() -> dict[int, int]:
    """Run nvidia-smi pmon to get per-process GPU SM utilization %.
    Returns a dict mapping PID -> sm_utilization_percent.
    """
    success, output = _run_nvidia_smi(["pmon", "-c", "1", "-s", "u"])
    result = {}
    if not success:
        return result
    for line in output.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 4:
            pid = _safe_int(fields[1])
            sm = _safe_int(fields[3], 0)
            if pid is not None:
                result[pid] = sm
    return result


def _categorize(name: str) -> str:
    if name and name.startswith("job_"):
        return "jobs"
    if name and name.startswith("ai_"):
        return "ai_agents"
    return "apps"


def get_gpu_breakdown() -> dict:
    if not _nvidia_smi_available():
        return {
            "available": False,
            "error": "nvidia-smi not found. NVIDIA GPU may not be installed.",
        }

    success, output = _run_nvidia_smi([
        "--query-compute-apps=pid,used_memory",
        "--format=csv,noheader,nounits",
    ])

    buckets = {
        "jobs": {"memory_used_mb": 0.0, "gpu_utilization_percent": 0},
        "apps": {"memory_used_mb": 0.0, "gpu_utilization_percent": 0},
        "ai_agents": {"memory_used_mb": 0.0, "gpu_utilization_percent": 0},
    }

    if not success:
        if "no running" in output.lower() or not output:
            return {"available": True, **buckets}
        return {"available": False, "error": output}

    pmon = _get_per_process_gpu_utilization()

    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                pid = int(parts[0])
                mem = _safe_float(parts[1]) or 0.0
            except (ValueError, TypeError):
                continue

            try:
                name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = ""

            cat = _categorize(name)
            buckets[cat]["memory_used_mb"] += mem
            buckets[cat]["gpu_utilization_percent"] += pmon.get(pid, 0)

    for cat in buckets:
        buckets[cat]["memory_used_mb"] = round(buckets[cat]["memory_used_mb"], 2)

    return {"available": True, **buckets}


def get_gpu_processes(limit: int = 20) -> dict:
    if not _nvidia_smi_available():
        return {
            "available": False,
            "error": "nvidia-smi not found. NVIDIA GPU may not be installed.",
            "processes": [],
            "total_count": 0,
        }

    success, output = _run_nvidia_smi([
        "--query-compute-apps=pid,name,gpu_uuid,used_memory",
        "--format=csv,noheader,nounits",
    ])

    if not success:
        if "no running" in output.lower() or not output:
            return {
                "available": True,
                "processes": [],
                "total_count": 0,
            }
        return {
            "available": False,
            "error": output,
            "processes": [],
            "total_count": 0,
        }

    pmon = _get_per_process_gpu_utilization()

    processes = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                pid = int(parts[0])
            except (ValueError, TypeError):
                continue

            processes.append({
                "pid": pid,
                "name": parts[1] if len(parts) > 1 else "Unknown",
                "gpu_uuid": parts[2] if len(parts) > 2 else "Unknown",
                "memory_used_mb": _safe_float(parts[3]) if len(parts) > 3 else None,
                "gpu_utilization_percent": pmon.get(pid, 0),
            })

    processes.sort(key=lambda p: p.get("memory_used_mb") or 0, reverse=True)
    total = len(processes)
    return {
        "available": True,
        "processes": processes[:limit],
        "total_count": total,
    }
