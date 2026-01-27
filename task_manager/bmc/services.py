import json
import os
import shutil
import subprocess

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = 1
QUEUE_KEY = "bmc:usage:history"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_bmc_history() -> dict:
    try:
        client = _get_redis_client()
        raw = client.lrange(QUEUE_KEY, 0, -1)
        history = [json.loads(entry) for entry in raw]
        return {"history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": [], "count": 0}


def _ipmitool_available() -> bool:
    return shutil.which("ipmitool") is not None


def _run_ipmitool(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["ipmitool"] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
    except FileNotFoundError:
        return False, "ipmitool not found"
    except subprocess.TimeoutExpired:
        return False, "ipmitool timed out"
    except Exception as e:
        return False, str(e)


def _safe_float(val, default=None):
    try:
        return float(val) if val and val.strip() not in ("na", "N/A", "[N/A]", "") else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=None):
    try:
        return int(float(val)) if val and val.strip() not in ("na", "N/A", "[N/A]", "") else default
    except (ValueError, TypeError):
        return default


def _parse_fru() -> dict:
    """Parse ipmitool fru print 0 for system identification."""
    success, output = _run_ipmitool(["fru", "print", "0"])
    info = {
        "manufacturer": None,
        "model": None,
        "serial": None,
        "asset_tag": None,
    }
    if not success:
        return info

    for line in output.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not value:
            continue
        if "product manufacturer" in key:
            info["manufacturer"] = value
        elif "product name" in key:
            info["model"] = value
        elif "product serial" in key:
            info["serial"] = value
        elif "product asset tag" in key:
            info["asset_tag"] = value
    return info


def _parse_chassis_status() -> dict:
    """Parse ipmitool chassis status for health overview."""
    success, output = _run_ipmitool(["chassis", "status"])
    status = {
        "power_state": None,
        "chassis_intrusion": None,
        "drive_fault": None,
        "cooling_fan_fault": None,
        "power_overload": None,
        "power_restore_policy": None,
        "front_panel_lockout": None,
        "main_power_fault": None,
    }
    if not success:
        return status

    for line in output.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if "system power" in key:
            status["power_state"] = value.upper()
        elif "chassis intrusion" in key:
            status["chassis_intrusion"] = value
        elif "drive fault" in key:
            status["drive_fault"] = value == "true"
        elif "cooling/fan fault" in key or "cooling fan fault" in key:
            status["cooling_fan_fault"] = value == "true"
        elif "power overload" in key:
            status["power_overload"] = value == "true"
        elif "power restore policy" in key:
            status["power_restore_policy"] = value
        elif "front-panel lockout" in key:
            status["front_panel_lockout"] = value
        elif "main power fault" in key:
            status["main_power_fault"] = value == "true"
    return status


def _parse_power_reading() -> dict:
    """Parse ipmitool dcmi power reading for power consumption."""
    success, output = _run_ipmitool(["dcmi", "power", "reading"])
    power = {
        "current_watts": None,
        "min_watts": None,
        "max_watts": None,
        "average_watts": None,
        "sampling_period_seconds": None,
    }
    if not success:
        return power

    for line in output.split("\n"):
        line_lower = line.strip().lower()
        if "instantaneous power reading" in line_lower:
            parts = line.split(":")
            if len(parts) >= 2:
                power["current_watts"] = _safe_int(parts[-1].replace("Watts", "").replace("watts", ""))
        elif "minimum during sampling" in line_lower:
            parts = line.split(":")
            if len(parts) >= 2:
                power["min_watts"] = _safe_int(parts[-1].replace("Watts", "").replace("watts", ""))
        elif "maximum during sampling" in line_lower:
            parts = line.split(":")
            if len(parts) >= 2:
                power["max_watts"] = _safe_int(parts[-1].replace("Watts", "").replace("watts", ""))
        elif "average power reading" in line_lower:
            parts = line.split(":")
            if len(parts) >= 2:
                power["average_watts"] = _safe_int(parts[-1].replace("Watts", "").replace("watts", ""))
        elif "sampling period" in line_lower and "seconds" in line_lower:
            parts = line.split(":")
            if len(parts) >= 2:
                val = parts[-1].strip().replace("Seconds.", "").replace("seconds.", "").strip()
                power["sampling_period_seconds"] = _safe_int(val)
    return power


def _parse_sensor_list() -> list[dict]:
    """Parse ipmitool sensor list into structured sensor data.
    Each line: Name | Value | Unit | Status | LNR | LC | LNC | UNC | UC | UNR
    """
    success, output = _run_ipmitool(["sensor", "list"])
    sensors = []
    if not success:
        return sensors

    for line in output.split("\n"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        name = parts[0]
        value = _safe_float(parts[1])
        unit = parts[2].strip() if len(parts) > 2 else ""
        status = parts[3].strip() if len(parts) > 3 else "na"

        sensor = {
            "name": name,
            "value": value,
            "unit": unit,
            "status": status,
        }
        if len(parts) >= 10:
            sensor["lower_non_recoverable"] = _safe_float(parts[4])
            sensor["lower_critical"] = _safe_float(parts[5])
            sensor["lower_non_critical"] = _safe_float(parts[6])
            sensor["upper_non_critical"] = _safe_float(parts[7])
            sensor["upper_critical"] = _safe_float(parts[8])
            sensor["upper_non_recoverable"] = _safe_float(parts[9])

        sensors.append(sensor)
    return sensors


def _parse_mc_info() -> dict:
    """Parse ipmitool mc info for BMC controller info."""
    success, output = _run_ipmitool(["mc", "info"])
    info = {
        "firmware_version": None,
        "ipmi_version": None,
        "manufacturer": None,
        "product": None,
    }
    if not success:
        return info

    for line in output.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if "firmware revision" in key:
            info["firmware_version"] = value
        elif "ipmi version" in key:
            info["ipmi_version"] = value
        elif "manufacturer name" in key:
            info["manufacturer"] = value
        elif "product name" in key:
            info["product"] = value
    return info


def get_bmc_status() -> dict:
    """Full BMC status: system info, health, power consumption, BMC controller info."""
    if not _ipmitool_available():
        return {
            "available": False,
            "error": "ipmitool not found. BMC/IPMI may not be available.",
        }

    system_info = _parse_fru()
    health = _parse_chassis_status()
    power = _parse_power_reading()
    bmc_info = _parse_mc_info()

    return {
        "available": True,
        "system_info": system_info,
        "health": health,
        "power_consumption": power,
        "bmc_info": bmc_info,
    }


def get_bmc_sensors() -> dict:
    """Detailed sensor readings grouped by type: thermals, fans, power_units, voltages."""
    if not _ipmitool_available():
        return {
            "available": False,
            "error": "ipmitool not found. BMC/IPMI may not be available.",
        }

    raw_sensors = _parse_sensor_list()

    thermals = []
    fans = []
    power_units = []
    voltages = []
    other = []

    for s in raw_sensors:
        unit = s.get("unit", "").lower()
        if "degrees c" in unit or "celsius" in unit:
            thermals.append({
                "name": s["name"],
                "temperature_c": s["value"],
                "status": s["status"],
                "upper_critical": s.get("upper_critical"),
                "upper_non_critical": s.get("upper_non_critical"),
            })
        elif "rpm" in unit:
            fans.append({
                "name": s["name"],
                "rpm": _safe_int(str(s["value"])) if s["value"] is not None else None,
                "status": s["status"],
                "lower_critical": s.get("lower_critical"),
                "lower_non_critical": s.get("lower_non_critical"),
            })
        elif "watts" in unit:
            power_units.append({
                "name": s["name"],
                "watts": s["value"],
                "status": s["status"],
                "upper_critical": s.get("upper_critical"),
                "upper_non_critical": s.get("upper_non_critical"),
            })
        elif "volts" in unit:
            voltages.append({
                "name": s["name"],
                "value": s["value"],
                "status": s["status"],
                "lower_critical": s.get("lower_critical"),
                "upper_critical": s.get("upper_critical"),
            })
        else:
            other.append(s)

    return {
        "available": True,
        "thermals": thermals,
        "fans": fans,
        "power_units": power_units,
        "voltages": voltages,
        "other": other,
    }


def get_bmc_sel(limit: int = 50) -> dict:
    """Retrieve System Event Log entries."""
    if not _ipmitool_available():
        return {
            "available": False,
            "error": "ipmitool not found. BMC/IPMI may not be available.",
            "events": [],
            "total_count": 0,
        }

    success, output = _run_ipmitool(["sel", "list"])
    if not success:
        if "no entries" in output.lower() or not output:
            return {
                "available": True,
                "events": [],
                "total_count": 0,
            }
        return {
            "available": False,
            "error": output,
            "events": [],
            "total_count": 0,
        }

    events = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            event = {
                "id": parts[0].strip(),
                "date": parts[1].strip() if len(parts) > 1 else None,
                "time": parts[2].strip() if len(parts) > 2 else None,
                "sensor": parts[3].strip() if len(parts) > 3 else None,
                "description": parts[4].strip() if len(parts) > 4 else None,
                "status": parts[5].strip() if len(parts) > 5 else None,
            }
            events.append(event)

    total = len(events)
    # SEL is chronological, reverse for newest-first
    events.reverse()
    return {
        "available": True,
        "events": events[:limit],
        "total_count": total,
    }
