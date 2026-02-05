import json
import os
import re
import subprocess
import time
from typing import Any

import psutil
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
ERROR_TTL = 600  # 10 minutes


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# Module-level state for tracking previous disk I/O samples
_prev_disk_io: dict[int, dict[str, int]] = {}
_prev_sample_time: float | None = None

# Module-level state for tracking per-process network I/O
_prev_net_io_per_pid: dict[int, dict[str, int]] = {}
_prev_net_io_time: float | None = None


def _bytes_to_mb(value: int) -> float:
    return round(value / (1024 * 1024), 2)


def _categorize_type(name: str) -> str:
    """Categorize process by name prefix."""
    if name and name.startswith("job_"):
        return "Job"
    if name and name.startswith("ai_"):
        return "AI Agent"
    return "App"


def get_unified_processes(limit: int = 50) -> dict[str, Any]:
    """
    Collect unified process data combining CPU, Memory, and Disk I/O.

    Uses two-phase collection: fast pass for all processes (lightweight fields),
    then expensive calls (io_counters) only for the top N by CPU usage.
    Parent/children are derived from a ppid map built in one O(n) pass.
    """
    global _prev_disk_io, _prev_sample_time

    current_time = time.time()
    delta_time = current_time - _prev_sample_time if _prev_sample_time else None
    cpu_count = psutil.cpu_count(logical=True) or 1

    # --- Phase 1: Fast pass over all processes ---
    lightweight = []
    children_map: dict[int, list] = {}
    all_names: dict[int, str] = {}

    for proc in psutil.process_iter([
        'pid', 'ppid', 'name', 'username', 'cpu_percent', 'memory_info', 'status'
    ]):
        try:
            info = proc.info
            pid = info['pid']
            name = info['name'] or ''
            ppid = info['ppid']
            mem_info = info.get('memory_info')

            all_names[pid] = name
            children_map.setdefault(ppid, []).append({'pid': pid, 'name': name})

            lightweight.append({
                'pid': pid,
                'ppid': ppid,
                'name': name,
                'username': info['username'] or '',
                'status': info['status'] or '',
                'cpu_percent': round((info['cpu_percent'] or 0.0) / cpu_count, 2),
                'mem_mb': _bytes_to_mb(mem_info.rss) if mem_info else 0.0,
                '_proc': proc,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    total_count = len(lightweight)

    # --- Phase 2: Sort and take top N ---
    lightweight.sort(key=lambda p: p['cpu_percent'], reverse=True)
    top_n = lightweight[:limit]

    # --- Phase 3: Enrich top N with expensive data ---
    current_disk_io: dict[int, dict[str, int]] = {}
    results = []

    for entry in top_n:
        pid = entry['pid']
        proc = entry.pop('_proc')

        # Disk I/O (only for top N)
        read_bytes = 0
        write_bytes = 0
        try:
            io = proc.io_counters()
            read_bytes = io.read_bytes
            write_bytes = io.write_bytes
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

        current_disk_io[pid] = {'read_bytes': read_bytes, 'write_bytes': write_bytes}

        disk_read_mbps = 0.0
        disk_write_mbps = 0.0
        if delta_time and delta_time > 0 and pid in _prev_disk_io:
            prev = _prev_disk_io[pid]
            read_delta = read_bytes - prev['read_bytes']
            write_delta = write_bytes - prev['write_bytes']
            if read_delta >= 0:
                disk_read_mbps = round(read_delta / delta_time / (1024 * 1024), 3)
            if write_delta >= 0:
                disk_write_mbps = round(write_delta / delta_time / (1024 * 1024), 3)

        # Parent from ppid map (O(1))
        ppid = entry['ppid']
        parent_name = all_names.get(ppid)
        parent = {'pid': ppid, 'name': parent_name} if parent_name else None

        # Children from ppid map (O(1))
        children = children_map.get(pid, [])

        results.append({
            'pid': pid,
            'ppid': ppid,
            'name': entry['name'],
            'type': _categorize_type(entry['name']),
            'execution': 'Centralized',
            'owner': entry['username'],
            'status': entry['status'],
            'cpu_percent': entry['cpu_percent'],
            'mem_mb': entry['mem_mb'],
            'disk_read_mbps': disk_read_mbps,
            'disk_write_mbps': disk_write_mbps,
            'parent': parent,
            'children': children,
        })

    _prev_disk_io = current_disk_io
    _prev_sample_time = current_time

    # Single ss call → per-process connections + network I/O rates
    top_pids = [r['pid'] for r in results]
    net_data = get_network_data(top_pids)
    for proc_entry in results:
        pid_net = net_data.get(proc_entry['pid'], {})
        proc_entry['connections'] = pid_net.get('connections', [])
        proc_entry['net_recv_kbps'] = pid_net.get('net_recv_kbps', 0.0)
        proc_entry['net_sent_kbps'] = pid_net.get('net_sent_kbps', 0.0)
        proc_entry['net_total_mb'] = pid_net.get('net_total_mb', 0.0)

    return {
        'processes': results,
        'total_count': total_count,
    }


_SS_PID_RE = re.compile(r'pid=(\d+)')
_SS_BYTES_SENT_RE = re.compile(r'bytes_sent:(\d+)')
_SS_BYTES_RECV_RE = re.compile(r'bytes_received:(\d+)')
_SS_CONN_RE = re.compile(
    r'^(\S+)\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+(.*)',
)


def _parse_ss_output() -> dict[int, dict]:
    """
    Single ss -tipn call → per-PID connections + cumulative byte counters.
    Returns {pid: {'bytes_sent': N, 'bytes_recv': N, 'connections': [...]}}
    """
    try:
        result = subprocess.run(
            ['ss', '-tipn'],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {}

    per_pid: dict[int, dict] = {}
    lines = result.stdout.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or line[0] in ('\t', ' ') or line.startswith('State'):
            i += 1
            continue

        pid_match = _SS_PID_RE.search(line)
        info_line = lines[i + 1] if i + 1 < len(lines) else ''

        if pid_match:
            pid = int(pid_match.group(1))

            # Parse connection details from the header line
            conn_match = _SS_CONN_RE.match(line)
            if conn_match:
                state = conn_match.group(1)
                local = conn_match.group(2)
                foreign = conn_match.group(3)
                conn_entry = {
                    'proto': 'TCP',
                    'local': local,
                    'foreign': foreign,
                    'state': state,
                }
            else:
                conn_entry = None

            # Parse byte counters from the info line
            sent_match = _SS_BYTES_SENT_RE.search(info_line)
            recv_match = _SS_BYTES_RECV_RE.search(info_line)
            sent = int(sent_match.group(1)) if sent_match else 0
            recv = int(recv_match.group(1)) if recv_match else 0

            if pid not in per_pid:
                per_pid[pid] = {'bytes_sent': 0, 'bytes_recv': 0, 'connections': []}

            per_pid[pid]['bytes_sent'] += sent
            per_pid[pid]['bytes_recv'] += recv
            if conn_entry:
                per_pid[pid]['connections'].append(conn_entry)

        i += 1
    return per_pid


def get_network_data(pids: list[int]) -> dict[int, dict]:
    """
    Single call: returns per-PID connections + network I/O rates.
    {pid: {'connections': [...], 'net_recv_kbps': N, 'net_sent_kbps': N, 'net_total_mb': N}}
    """
    global _prev_net_io_per_pid, _prev_net_io_time

    current_time = time.time()
    ss_data = _parse_ss_output()
    delta = current_time - _prev_net_io_time if _prev_net_io_time else None

    result = {}
    for pid in pids:
        entry = ss_data.get(pid, {'bytes_sent': 0, 'bytes_recv': 0, 'connections': []})
        net_recv_kbps = 0.0
        net_sent_kbps = 0.0
        total_mb = round((entry['bytes_sent'] + entry['bytes_recv']) / (1024 * 1024), 2)

        if delta and delta > 0 and pid in _prev_net_io_per_pid:
            prev = _prev_net_io_per_pid[pid]
            recv_delta = entry['bytes_recv'] - prev.get('bytes_recv', 0)
            sent_delta = entry['bytes_sent'] - prev.get('bytes_sent', 0)
            if recv_delta >= 0:
                net_recv_kbps = round(recv_delta / delta / 1024, 2)
            if sent_delta >= 0:
                net_sent_kbps = round(sent_delta / delta / 1024, 2)

        result[pid] = {
            'connections': entry['connections'],
            'net_recv_kbps': net_recv_kbps,
            'net_sent_kbps': net_sent_kbps,
            'net_total_mb': total_mb,
        }

    _prev_net_io_per_pid = {
        pid: {'bytes_sent': d['bytes_sent'], 'bytes_recv': d['bytes_recv']}
        for pid, d in ss_data.items()
    }
    _prev_net_io_time = current_time
    return result


def refresh_error_cache(pids: list[int]) -> None:
    """Fetch errors from journald for given PIDs and cache summaries in Redis."""
    try:
        client = _get_redis_client()
    except redis.RedisError:
        return

    for pid in pids:
        try:
            errors = _fetch_journal_errors(pid)
            error_count = len(errors)
            last_error = errors[-1]["message"] if errors else None

            if error_count == 0:
                health = "healthy"
            elif error_count <= 5:
                health = "warning"
            else:
                health = "degraded"

            summary = json.dumps({
                "error_count": error_count,
                "health": health,
                "last_error": last_error,
            })
            client.set(f"proc:error_summary:{pid}", summary, ex=ERROR_TTL)
        except (redis.RedisError, Exception):
            continue


def get_cached_error_summaries(pids: list[int]) -> dict[int, dict]:
    """Read cached error summaries from Redis. Returns {pid: {error_count, health}}."""
    result = {}
    try:
        client = _get_redis_client()
        pipe = client.pipeline()
        for pid in pids:
            pipe.get(f"proc:error_summary:{pid}")
        values = pipe.execute()

        for pid, raw in zip(pids, values):
            if raw:
                result[pid] = json.loads(raw)
            else:
                result[pid] = {"error_count": 0, "health": "healthy", "last_error": None}
    except redis.RedisError:
        for pid in pids:
            result[pid] = {"error_count": 0, "health": "healthy", "last_error": None}
    return result


def _fetch_journal_errors(pid: int, since: str = "10m ago") -> list[dict]:
    """Fetch error-level messages from journald for a given PID."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                f"_PID={pid}",
                f"--since={since}",
                "--priority=err",
                "--output=json",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        errors = []
        for line in result.stdout.strip().splitlines():
            try:
                entry = json.loads(line)
                errors.append({
                    "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                    "message": entry.get("MESSAGE", ""),
                    "priority": entry.get("PRIORITY", ""),
                })
            except json.JSONDecodeError:
                continue
        return errors
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def get_process_errors(pid: int) -> dict[str, Any]:
    """
    Get error info for a process: count, trend, last error, health.
    Uses Redis to cache and track error counts over time.
    """
    redis_key = f"proc:errors:{pid}"
    prev_count_key = f"proc:errors:prev_count:{pid}"

    # Fetch current errors from journald
    errors = _fetch_journal_errors(pid)
    error_count = len(errors)
    last_error = errors[-1]["message"] if errors else None

    # Store current errors in Redis
    try:
        client = _get_redis_client()
        client.set(redis_key, json.dumps(errors), ex=ERROR_TTL)

        # Determine trend by comparing with previous count
        prev_raw = client.get(prev_count_key)
        prev_count = int(prev_raw) if prev_raw else 0

        if error_count > prev_count:
            trend = "increasing"
        elif error_count < prev_count:
            trend = "decreasing"
        else:
            trend = "stable"

        # Store current count as previous for next request
        client.set(prev_count_key, error_count, ex=ERROR_TTL)
    except redis.RedisError:
        trend = "unknown"

    # Derive health status
    if error_count == 0:
        health = "healthy"
    elif error_count <= 5:
        health = "warning"
    else:
        health = "degraded"

    return {
        "pid": pid,
        "error_count": error_count,
        "window": "10m",
        "trend": trend,
        "last_error": last_error,
        "health": health,
        "errors": errors[-10:],  # Last 10 error entries
    }
