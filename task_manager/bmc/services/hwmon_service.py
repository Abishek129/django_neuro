"""
Hardware Monitoring Service
Reads fan RPM, temperatures, and controls fan speeds via hwmon/lm-sensors
Also supports IPMI/BMC data when available (requires root privileges)
"""
import json
import subprocess
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import asyncio
from contextlib import contextmanager
import re

# Database path
DB_PATH = os.getenv("HWMON_DB_PATH", str(Path(__file__).parent / "hwmon_metrics.db"))

# Logging interval in seconds
LOG_INTERVAL = int(os.getenv("HWMON_LOG_INTERVAL", "30"))


def init_database():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sensor_type TEXT NOT NULL,
            chip TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            label TEXT,
            value REAL NOT NULL,
            unit TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_logs_timestamp
        ON sensor_logs(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_logs_type_name
        ON sensor_logs(sensor_type, sensor_name)
    """)

    # Table for intrusion detection events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intrusion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chip TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            alarm_state INTEGER NOT NULL,
            beep_enabled INTEGER
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_intrusion_logs_timestamp
        ON intrusion_logs(timestamp)
    """)

    # Table for PWM/fan control state logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pwm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chip TEXT NOT NULL,
            pwm_name TEXT NOT NULL,
            pwm_value INTEGER NOT NULL,
            pwm_percent REAL NOT NULL,
            enable_mode INTEGER NOT NULL,
            enable_mode_name TEXT,
            fan_rpm INTEGER
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pwm_logs_timestamp
        ON pwm_logs(timestamp)
    """)

    # Table for alarm/alert events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chip TEXT NOT NULL,
            sensor_type TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            alarm_type TEXT NOT NULL,
            alarm_state INTEGER NOT NULL,
            sensor_value REAL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alarm_logs_timestamp
        ON alarm_logs(timestamp)
    """)

    # Table for beep/alert configuration state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beep_config_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chip TEXT NOT NULL,
            beep_enable INTEGER NOT NULL
        )
    """)

    # Table for custom sensor labels/aliases
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_type TEXT NOT NULL,
            chip TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            custom_label TEXT NOT NULL,
            description TEXT,
            location TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sensor_type, chip, sensor_name)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sensor_aliases_lookup
        ON sensor_aliases(sensor_type, chip, sensor_name)
    """)

    conn.commit()
    conn.close()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_sensors_data() -> dict:
    """Get all sensor data from lm-sensors."""
    try:
        result = subprocess.run(
            ["sensors", "-j"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return {}


def parse_sensors() -> dict:
    """Parse sensor data into a structured format."""
    raw_data = get_sensors_data()

    fans = []
    temperatures = []
    voltages = []
    pwm_controls = []
    intrusions = []
    alarms = []
    beep_config = None

    for chip_name, chip_data in raw_data.items():
        adapter = chip_data.get("Adapter", "Unknown")

        for sensor_name, sensor_data in chip_data.items():
            if sensor_name == "Adapter":
                continue

            if not isinstance(sensor_data, dict):
                continue

            # Process intrusion sensors
            if sensor_name.startswith("intrusion"):
                intrusions.append({
                    "chip": chip_name,
                    "name": sensor_name,
                    "alarm": int(sensor_data.get(f"{sensor_name}_alarm", 0)),
                    "beep": int(sensor_data.get(f"{sensor_name}_beep", 0))
                })
                continue

            # Process beep_enable
            if sensor_name == "beep_enable":
                beep_config = {
                    "chip": chip_name,
                    "enabled": int(sensor_data.get("beep_enable", 0))
                }
                continue

            # Process fan sensors
            for key, value in sensor_data.items():
                if key.endswith("_input"):
                    base_key = key.replace("_input", "")

                    if "fan" in key:
                        fan_alarm = sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                        fans.append({
                            "chip": chip_name,
                            "adapter": adapter,
                            "name": base_key,
                            "label": sensor_name,
                            "rpm": value,
                            "min": sensor_data.get(f"{base_key}_min", 0),
                            "alarm": fan_alarm,
                            "beep": int(sensor_data.get(f"{base_key}_beep", 0)),
                            "pulses": int(sensor_data.get(f"{base_key}_pulses", 2))
                        })
                        # Track alarm state
                        if fan_alarm:
                            alarms.append({
                                "chip": chip_name,
                                "sensor_type": "fan",
                                "sensor_name": base_key,
                                "alarm_type": "fan_alarm",
                                "alarm_state": 1,
                                "sensor_value": value
                            })
                    elif "temp" in key:
                        temp_alarm = sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                        temperatures.append({
                            "chip": chip_name,
                            "adapter": adapter,
                            "name": base_key,
                            "label": sensor_name,
                            "current": value,
                            "max": sensor_data.get(f"{base_key}_max"),
                            "crit": sensor_data.get(f"{base_key}_crit"),
                            "max_hyst": sensor_data.get(f"{base_key}_max_hyst"),
                            "alarm": temp_alarm,
                            "beep": int(sensor_data.get(f"{base_key}_beep", 0)),
                            "type": int(sensor_data.get(f"{base_key}_type", 0)),
                            "offset": sensor_data.get(f"{base_key}_offset", 0)
                        })
                        # Track alarm state
                        if temp_alarm:
                            alarms.append({
                                "chip": chip_name,
                                "sensor_type": "temperature",
                                "sensor_name": base_key,
                                "alarm_type": "temp_alarm",
                                "alarm_state": 1,
                                "sensor_value": value
                            })
                    elif "in" in key:
                        volt_alarm = sensor_data.get(f"{base_key}_alarm", 0) == 1.0
                        voltages.append({
                            "chip": chip_name,
                            "adapter": adapter,
                            "name": base_key,
                            "label": sensor_name,
                            "voltage": value,
                            "min": sensor_data.get(f"{base_key}_min"),
                            "max": sensor_data.get(f"{base_key}_max"),
                            "alarm": volt_alarm,
                            "beep": int(sensor_data.get(f"{base_key}_beep", 0))
                        })
                        # Track alarm state
                        if volt_alarm:
                            alarms.append({
                                "chip": chip_name,
                                "sensor_type": "voltage",
                                "sensor_name": base_key,
                                "alarm_type": "voltage_alarm",
                                "alarm_state": 1,
                                "sensor_value": value
                            })

            # Process PWM controls
            for key, value in sensor_data.items():
                if key.startswith("pwm") and "_" not in key:
                    pwm_num = key.replace("pwm", "")
                    enable_val = int(sensor_data.get(f"pwm{pwm_num}_enable", 0))
                    pwm_controls.append({
                        "chip": chip_name,
                        "name": key,
                        "label": sensor_name,
                        "value": value,
                        "percent": round((value / 255) * 100, 1),
                        "enable": enable_val,
                        "enable_mode_name": get_enable_mode_name(enable_val),
                        "mode": sensor_data.get(f"pwm{pwm_num}_mode", 0)
                    })

    return {
        "fans": fans,
        "temperatures": temperatures,
        "voltages": voltages,
        "pwm_controls": pwm_controls,
        "intrusions": intrusions,
        "alarms": alarms,
        "beep_config": beep_config,
        "timestamp": datetime.now().isoformat()
    }


def find_hwmon_path(chip_name: str) -> Optional[Path]:
    """Find the hwmon sysfs path for a given chip."""
    hwmon_base = Path("/sys/class/hwmon")

    for hwmon_dir in hwmon_base.iterdir():
        name_file = hwmon_dir / "name"
        if name_file.exists():
            try:
                with open(name_file) as f:
                    name = f.read().strip()
                    # Match chip names like "nct6798" from "nct6798-isa-0290"
                    if name in chip_name or chip_name.startswith(name):
                        return hwmon_dir
            except IOError:
                continue

    return None


def get_pwm_controls() -> list:
    """Get all available PWM fan controls."""
    hwmon_base = Path("/sys/class/hwmon")
    controls = []

    for hwmon_dir in hwmon_base.iterdir():
        name_file = hwmon_dir / "name"
        chip_name = "unknown"
        if name_file.exists():
            try:
                with open(name_file) as f:
                    chip_name = f.read().strip()
            except IOError:
                pass

        # Find all PWM files
        for pwm_file in hwmon_dir.glob("pwm[0-9]"):
            pwm_name = pwm_file.name
            enable_file = hwmon_dir / f"{pwm_name}_enable"

            try:
                with open(pwm_file) as f:
                    pwm_value = int(f.read().strip())

                enable_value = 0
                if enable_file.exists():
                    with open(enable_file) as f:
                        enable_value = int(f.read().strip())

                # Find associated fan
                fan_num = pwm_name.replace("pwm", "")
                fan_input = hwmon_dir / f"fan{fan_num}_input"
                fan_rpm = 0
                if fan_input.exists():
                    with open(fan_input) as f:
                        fan_rpm = int(f.read().strip())

                # Get fan label if available
                fan_label_file = hwmon_dir / f"fan{fan_num}_label"
                fan_label = f"fan{fan_num}"
                if fan_label_file.exists():
                    with open(fan_label_file) as f:
                        fan_label = f.read().strip()

                controls.append({
                    "chip": chip_name,
                    "hwmon_path": str(hwmon_dir),
                    "pwm_name": pwm_name,
                    "pwm_value": pwm_value,
                    "pwm_percent": round((pwm_value / 255) * 100, 1),
                    "enable": enable_value,
                    "enable_mode": get_enable_mode_name(enable_value),
                    "fan_rpm": fan_rpm,
                    "fan_label": fan_label,
                    "controllable": enable_value == 1  # Manual mode
                })
            except (IOError, ValueError):
                continue

    return controls


def get_enable_mode_name(enable_value: int) -> str:
    """Convert pwm_enable value to human-readable mode name."""
    modes = {
        0: "off",
        1: "manual",
        2: "thermal_cruise",
        3: "speed_cruise",
        4: "smart_fan_iv",
        5: "smart_fan_bios"
    }
    return modes.get(enable_value, f"unknown({enable_value})")


def set_pwm_value(hwmon_path: str, pwm_name: str, value: int) -> dict:
    """
    Set PWM value for a fan.
    Requires the pwm_enable to be set to 1 (manual mode) first.
    Value should be 0-255.
    """
    import time

    pwm_path = Path(hwmon_path) / pwm_name
    enable_path = Path(hwmon_path) / f"{pwm_name}_enable"

    if not pwm_path.exists():
        return {"success": False, "error": f"PWM path not found: {pwm_path}"}

    # Clamp value
    value = max(0, min(255, value))

    try:
        # Try to set manual mode and PWM value multiple times
        # Some chips (like NCT6798 on ASUS boards) have EC override that resets the mode
        for attempt in range(3):
            # Set manual mode
            if enable_path.exists():
                with open(enable_path, "w") as f:
                    f.write("1")
                    f.flush()

            # Immediately set PWM value
            with open(pwm_path, "w") as f:
                f.write(str(value))
                f.flush()

            # Small delay
            time.sleep(0.05)

            # Verify the write stuck
            with open(enable_path) as f:
                current_enable = int(f.read().strip())
            with open(pwm_path) as f:
                current_value = int(f.read().strip())

            if current_enable == 1 and current_value == value:
                return {
                    "success": True,
                    "pwm_name": pwm_name,
                    "value": value,
                    "percent": round((value / 255) * 100, 1)
                }

        # If we get here, the EC is overriding our writes
        return {
            "success": False,
            "error": f"Fan control is locked by motherboard EC. The PWM writes are being overridden. "
                     f"Check BIOS for fan control settings or try disabling EC fan management. "
                     f"Current state: enable={current_enable}, pwm={current_value}",
            "ec_override": True,
            "current_enable": current_enable,
            "current_value": current_value
        }
    except PermissionError:
        return {
            "success": False,
            "error": "Permission denied. Need root privileges to control fans."
        }
    except IOError as e:
        return {"success": False, "error": str(e)}


def set_pwm_mode(hwmon_path: str, pwm_name: str, mode: int) -> dict:
    """
    Set PWM control mode.
    0 = off (fan full speed)
    1 = manual
    2 = thermal cruise
    5 = smart fan (BIOS control)
    """
    import time

    enable_path = Path(hwmon_path) / f"{pwm_name}_enable"

    if not enable_path.exists():
        return {"success": False, "error": "PWM enable path not found"}

    try:
        # Try multiple times to set the mode
        for attempt in range(3):
            with open(enable_path, "w") as f:
                f.write(str(mode))
                f.flush()

            time.sleep(0.05)

            # Verify the write stuck
            with open(enable_path) as f:
                current_mode = int(f.read().strip())

            if current_mode == mode:
                return {
                    "success": True,
                    "pwm_name": pwm_name,
                    "mode": mode,
                    "mode_name": get_enable_mode_name(mode)
                }

        # EC is overriding
        return {
            "success": False,
            "error": f"Fan mode is locked by motherboard EC. Mode reverted to {get_enable_mode_name(current_mode)}. "
                     f"Check BIOS for fan control settings.",
            "ec_override": True,
            "actual_mode": current_mode,
            "actual_mode_name": get_enable_mode_name(current_mode)
        }
    except PermissionError:
        return {
            "success": False,
            "error": "Permission denied. Need root privileges to change fan mode."
        }
    except IOError as e:
        return {"success": False, "error": str(e)}


def log_current_metrics():
    """Log current sensor readings to the database."""
    data = parse_sensors()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()

        # Log fans
        for fan in data["fans"]:
            cursor.execute("""
                INSERT INTO sensor_logs (timestamp, sensor_type, chip, sensor_name, label, value, unit)
                VALUES (?, 'fan', ?, ?, ?, ?, 'RPM')
            """, (timestamp, fan["chip"], fan["name"], fan["label"], fan["rpm"]))

        # Log temperatures
        for temp in data["temperatures"]:
            cursor.execute("""
                INSERT INTO sensor_logs (timestamp, sensor_type, chip, sensor_name, label, value, unit)
                VALUES (?, 'temperature', ?, ?, ?, ?, '°C')
            """, (timestamp, temp["chip"], temp["name"], temp["label"], temp["current"]))

        # Log voltages
        for voltage in data["voltages"]:
            cursor.execute("""
                INSERT INTO sensor_logs (timestamp, sensor_type, chip, sensor_name, label, value, unit)
                VALUES (?, 'voltage', ?, ?, ?, ?, 'V')
            """, (timestamp, voltage["chip"], voltage["name"], voltage["label"], voltage["voltage"]))

        # Log intrusion detection events
        for intrusion in data["intrusions"]:
            cursor.execute("""
                INSERT INTO intrusion_logs (timestamp, chip, sensor_name, alarm_state, beep_enabled)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, intrusion["chip"], intrusion["name"],
                  intrusion["alarm"], intrusion["beep"]))

        # Log PWM/fan control states
        for pwm in data["pwm_controls"]:
            # Find associated fan RPM
            fan_rpm = 0
            pwm_num = pwm["name"].replace("pwm", "")
            for fan in data["fans"]:
                if fan["name"] == f"fan{pwm_num}" and fan["chip"] == pwm["chip"]:
                    fan_rpm = fan["rpm"]
                    break

            cursor.execute("""
                INSERT INTO pwm_logs (timestamp, chip, pwm_name, pwm_value, pwm_percent,
                                      enable_mode, enable_mode_name, fan_rpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, pwm["chip"], pwm["name"], int(pwm["value"]),
                  pwm["percent"], pwm["enable"], pwm["enable_mode_name"], fan_rpm))

        # Log alarms
        for alarm in data["alarms"]:
            cursor.execute("""
                INSERT INTO alarm_logs (timestamp, chip, sensor_type, sensor_name,
                                        alarm_type, alarm_state, sensor_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, alarm["chip"], alarm["sensor_type"], alarm["sensor_name"],
                  alarm["alarm_type"], alarm["alarm_state"], alarm["sensor_value"]))

        # Log beep configuration
        if data["beep_config"]:
            cursor.execute("""
                INSERT INTO beep_config_logs (timestamp, chip, beep_enable)
                VALUES (?, ?, ?)
            """, (timestamp, data["beep_config"]["chip"], data["beep_config"]["enabled"]))

        conn.commit()


def get_historical_data(
    sensor_type: Optional[str] = None,
    sensor_name: Optional[str] = None,
    hours: int = 24,
    limit: int = 1000
) -> list:
    """Get historical sensor data from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT timestamp, sensor_type, chip, sensor_name, label, value, unit
            FROM sensor_logs
            WHERE timestamp > datetime('now', ?)
        """
        params = [f'-{hours} hours']

        if sensor_type:
            query += " AND sensor_type = ?"
            params.append(sensor_type)

        if sensor_name:
            query += " AND sensor_name = ?"
            params.append(sensor_name)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]


def get_aggregated_data(
    sensor_type: str,
    hours: int = 24,
    interval_minutes: int = 5
) -> list:
    """Get aggregated sensor data for charts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # SQLite datetime grouping by interval
        cursor.execute("""
            SELECT
                strftime('%Y-%m-%d %H:', timestamp) ||
                    (CAST(strftime('%M', timestamp) AS INTEGER) / ?) * ? || ':00' as time_bucket,
                sensor_name,
                label,
                AVG(value) as avg_value,
                MIN(value) as min_value,
                MAX(value) as max_value,
                unit
            FROM sensor_logs
            WHERE timestamp > datetime('now', ?)
                AND sensor_type = ?
            GROUP BY time_bucket, sensor_name
            ORDER BY time_bucket DESC
        """, (interval_minutes, interval_minutes, f'-{hours} hours', sensor_type))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def cleanup_old_logs(days: int = 30):
    """Remove logs older than specified days."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        total_deleted = 0

        # Clean all log tables
        for table in ['sensor_logs', 'intrusion_logs', 'pwm_logs', 'alarm_logs', 'beep_config_logs']:
            cursor.execute(f"""
                DELETE FROM {table}
                WHERE timestamp < datetime('now', ?)
            """, (f'-{days} days',))
            total_deleted += cursor.rowcount

        conn.commit()
        return total_deleted


def get_intrusion_history(hours: int = 24, limit: int = 1000) -> list:
    """Get intrusion detection history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, chip, sensor_name, alarm_state, beep_enabled
            FROM intrusion_logs
            WHERE timestamp > datetime('now', ?)
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f'-{hours} hours', limit))
        return [dict(row) for row in cursor.fetchall()]


def get_pwm_history(hours: int = 24, pwm_name: Optional[str] = None, limit: int = 1000) -> list:
    """Get PWM/fan control state history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT timestamp, chip, pwm_name, pwm_value, pwm_percent,
                   enable_mode, enable_mode_name, fan_rpm
            FROM pwm_logs
            WHERE timestamp > datetime('now', ?)
        """
        params = [f'-{hours} hours']

        if pwm_name:
            query += " AND pwm_name = ?"
            params.append(pwm_name)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_alarm_history(hours: int = 24, sensor_type: Optional[str] = None, limit: int = 1000) -> list:
    """Get alarm event history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT timestamp, chip, sensor_type, sensor_name, alarm_type, alarm_state, sensor_value
            FROM alarm_logs
            WHERE timestamp > datetime('now', ?)
        """
        params = [f'-{hours} hours']

        if sensor_type:
            query += " AND sensor_type = ?"
            params.append(sensor_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_beep_config_history(hours: int = 24, limit: int = 100) -> list:
    """Get beep configuration history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, chip, beep_enable
            FROM beep_config_logs
            WHERE timestamp > datetime('now', ?)
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f'-{hours} hours', limit))
        return [dict(row) for row in cursor.fetchall()]


# ============== Sensor Aliases/Labels ==============

def get_all_aliases() -> list:
    """Get all sensor aliases/custom labels."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sensor_type, chip, sensor_name, custom_label, description, location,
                   created_at, updated_at
            FROM sensor_aliases
            ORDER BY sensor_type, chip, sensor_name
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_alias(sensor_type: str, chip: str, sensor_name: str) -> Optional[dict]:
    """Get alias for a specific sensor."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sensor_type, chip, sensor_name, custom_label, description, location,
                   created_at, updated_at
            FROM sensor_aliases
            WHERE sensor_type = ? AND chip = ? AND sensor_name = ?
        """, (sensor_type, chip, sensor_name))
        row = cursor.fetchone()
        return dict(row) if row else None


def set_alias(
    sensor_type: str,
    chip: str,
    sensor_name: str,
    custom_label: str,
    description: Optional[str] = None,
    location: Optional[str] = None
) -> dict:
    """Set or update alias for a sensor."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sensor_aliases (sensor_type, chip, sensor_name, custom_label, description, location)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sensor_type, chip, sensor_name)
            DO UPDATE SET
                custom_label = excluded.custom_label,
                description = excluded.description,
                location = excluded.location,
                updated_at = CURRENT_TIMESTAMP
        """, (sensor_type, chip, sensor_name, custom_label, description, location))
        conn.commit()
        return {
            "sensor_type": sensor_type,
            "chip": chip,
            "sensor_name": sensor_name,
            "custom_label": custom_label,
            "description": description,
            "location": location
        }


def delete_alias(sensor_type: str, chip: str, sensor_name: str) -> bool:
    """Delete alias for a sensor."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM sensor_aliases
            WHERE sensor_type = ? AND chip = ? AND sensor_name = ?
        """, (sensor_type, chip, sensor_name))
        conn.commit()
        return cursor.rowcount > 0


def get_aliases_map() -> dict:
    """Get aliases as a lookup map for quick access."""
    aliases = get_all_aliases()
    alias_map = {}
    for alias in aliases:
        key = f"{alias['sensor_type']}:{alias['chip']}:{alias['sensor_name']}"
        alias_map[key] = alias
    return alias_map


def apply_aliases_to_sensors(data: dict) -> dict:
    """Apply custom aliases to sensor data."""
    alias_map = get_aliases_map()

    # Apply to fans
    for fan in data.get("fans", []):
        key = f"fan:{fan['chip']}:{fan['name']}"
        if key in alias_map:
            fan["custom_label"] = alias_map[key]["custom_label"]
            fan["description"] = alias_map[key]["description"]
            fan["location"] = alias_map[key]["location"]

    # Apply to temperatures
    for temp in data.get("temperatures", []):
        key = f"temperature:{temp['chip']}:{temp['name']}"
        if key in alias_map:
            temp["custom_label"] = alias_map[key]["custom_label"]
            temp["description"] = alias_map[key]["description"]
            temp["location"] = alias_map[key]["location"]

    # Apply to voltages
    for volt in data.get("voltages", []):
        key = f"voltage:{volt['chip']}:{volt['name']}"
        if key in alias_map:
            volt["custom_label"] = alias_map[key]["custom_label"]
            volt["description"] = alias_map[key]["description"]
            volt["location"] = alias_map[key]["location"]

    # Apply to PWM controls
    for pwm in data.get("pwm_controls", []):
        key = f"pwm:{pwm['chip']}:{pwm['name']}"
        if key in alias_map:
            pwm["custom_label"] = alias_map[key]["custom_label"]
            pwm["description"] = alias_map[key]["description"]
            pwm["location"] = alias_map[key]["location"]

    # Apply to intrusions
    for intrusion in data.get("intrusions", []):
        key = f"intrusion:{intrusion['chip']}:{intrusion['name']}"
        if key in alias_map:
            intrusion["custom_label"] = alias_map[key]["custom_label"]
            intrusion["description"] = alias_map[key]["description"]
            intrusion["location"] = alias_map[key]["location"]

    return data


def list_available_sensors() -> dict:
    """List all available sensors that can be labeled."""
    data = parse_sensors()
    alias_map = get_aliases_map()

    sensors = []

    # Collect fans
    for fan in data.get("fans", []):
        key = f"fan:{fan['chip']}:{fan['name']}"
        alias = alias_map.get(key)
        sensors.append({
            "sensor_type": "fan",
            "chip": fan["chip"],
            "sensor_name": fan["name"],
            "default_label": fan["label"],
            "current_value": fan["rpm"],
            "unit": "RPM",
            "custom_label": alias["custom_label"] if alias else None,
            "description": alias["description"] if alias else None,
            "location": alias["location"] if alias else None
        })

    # Collect temperatures
    for temp in data.get("temperatures", []):
        key = f"temperature:{temp['chip']}:{temp['name']}"
        alias = alias_map.get(key)
        sensors.append({
            "sensor_type": "temperature",
            "chip": temp["chip"],
            "sensor_name": temp["name"],
            "default_label": temp["label"],
            "current_value": temp["current"],
            "unit": "°C",
            "custom_label": alias["custom_label"] if alias else None,
            "description": alias["description"] if alias else None,
            "location": alias["location"] if alias else None
        })

    # Collect voltages
    for volt in data.get("voltages", []):
        key = f"voltage:{volt['chip']}:{volt['name']}"
        alias = alias_map.get(key)
        sensors.append({
            "sensor_type": "voltage",
            "chip": volt["chip"],
            "sensor_name": volt["name"],
            "default_label": volt["label"],
            "current_value": volt["voltage"],
            "unit": "V",
            "custom_label": alias["custom_label"] if alias else None,
            "description": alias["description"] if alias else None,
            "location": alias["location"] if alias else None
        })

    # Collect PWM controls
    for pwm in data.get("pwm_controls", []):
        key = f"pwm:{pwm['chip']}:{pwm['name']}"
        alias = alias_map.get(key)
        sensors.append({
            "sensor_type": "pwm",
            "chip": pwm["chip"],
            "sensor_name": pwm["name"],
            "default_label": pwm["label"],
            "current_value": pwm["percent"],
            "unit": "%",
            "custom_label": alias["custom_label"] if alias else None,
            "description": alias["description"] if alias else None,
            "location": alias["location"] if alias else None
        })

    # Collect intrusions
    for intrusion in data.get("intrusions", []):
        key = f"intrusion:{intrusion['chip']}:{intrusion['name']}"
        alias = alias_map.get(key)
        sensors.append({
            "sensor_type": "intrusion",
            "chip": intrusion["chip"],
            "sensor_name": intrusion["name"],
            "default_label": intrusion["name"],
            "current_value": intrusion["alarm"],
            "unit": "alarm",
            "custom_label": alias["custom_label"] if alias else None,
            "description": alias["description"] if alias else None,
            "location": alias["location"] if alias else None
        })

    return {
        "sensors": sensors,
        "count": len(sensors),
        "timestamp": datetime.now().isoformat()
    }


# ============== IPMI/BMC Integration ==============

def check_ipmi_available() -> bool:
    """Check if IPMI tools are available and accessible."""
    try:
        result = subprocess.run(
            ["ipmitool", "mc", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_ipmi_sensors() -> list:
    """Get all IPMI sensor readings."""
    try:
        result = subprocess.run(
            ["ipmitool", "sensor", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []

        sensors = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                name = parts[0]
                value = parts[1]
                unit = parts[2]
                status = parts[3]

                # Parse numeric value
                try:
                    numeric_value = float(value) if value and value != 'na' else None
                except ValueError:
                    numeric_value = None

                sensors.append({
                    "name": name,
                    "value": numeric_value,
                    "raw_value": value,
                    "unit": unit,
                    "status": status
                })
        return sensors
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_ipmi_chassis_status() -> dict:
    """Get chassis status from IPMI."""
    try:
        result = subprocess.run(
            ["ipmitool", "chassis", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return {"available": False, "error": result.stderr}

        status = {"available": True}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                status[key] = value
        return status
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"available": False, "error": "IPMI not available"}


def get_ipmi_sel(count: int = 20) -> list:
    """Get recent System Event Log entries from IPMI."""
    try:
        result = subprocess.run(
            ["ipmitool", "sel", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []

        events = []
        for line in result.stdout.strip().split('\n')[-count:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                events.append({
                    "id": parts[0],
                    "timestamp": parts[1] if len(parts) > 1 else "",
                    "sensor": parts[2] if len(parts) > 2 else "",
                    "event": parts[3] if len(parts) > 3 else "",
                    "raw": line
                })
        return events
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_system_info() -> dict:
    """Get system/chassis information from DMI."""
    info = {
        "chassis_type": None,
        "board_name": None,
        "board_vendor": None,
        "board_version": None,
        "bios_vendor": None,
        "bios_version": None,
        "bios_date": None
    }

    dmi_mappings = {
        "chassis_type": "/sys/class/dmi/id/chassis_type",
        "board_name": "/sys/class/dmi/id/board_name",
        "board_vendor": "/sys/class/dmi/id/board_vendor",
        "board_version": "/sys/class/dmi/id/board_version",
        "bios_vendor": "/sys/class/dmi/id/bios_vendor",
        "bios_version": "/sys/class/dmi/id/bios_version",
        "bios_date": "/sys/class/dmi/id/bios_date"
    }

    chassis_types = {
        "1": "Other", "2": "Unknown", "3": "Desktop", "4": "Low Profile Desktop",
        "5": "Pizza Box", "6": "Mini Tower", "7": "Tower", "8": "Portable",
        "9": "Laptop", "10": "Notebook", "11": "Hand Held", "12": "Docking Station",
        "13": "All in One", "14": "Sub Notebook", "15": "Space-saving",
        "16": "Lunch Box", "17": "Main Server Chassis", "18": "Expansion Chassis",
        "19": "SubChassis", "20": "Bus Expansion Chassis", "21": "Peripheral Chassis",
        "22": "RAID Chassis", "23": "Rack Mount Chassis"
    }

    for key, path in dmi_mappings.items():
        try:
            with open(path) as f:
                value = f.read().strip()
                if key == "chassis_type":
                    info[key] = chassis_types.get(value, value)
                    info["chassis_type_raw"] = value
                else:
                    info[key] = value if value and value != "Default string" else None
        except (IOError, PermissionError):
            pass

    return info


def get_power_status() -> dict:
    """Get power supply and ACPI status."""
    status = {
        "ac_online": None,
        "batteries": [],
        "thermal_zones": []
    }

    # Check AC adapter
    ac_path = Path("/sys/class/power_supply/AC")
    if ac_path.exists():
        try:
            with open(ac_path / "online") as f:
                status["ac_online"] = f.read().strip() == "1"
        except IOError:
            pass

    # Check batteries
    ps_path = Path("/sys/class/power_supply")
    if ps_path.exists():
        for supply in ps_path.iterdir():
            type_file = supply / "type"
            if type_file.exists():
                try:
                    with open(type_file) as f:
                        if f.read().strip() == "Battery":
                            battery = {"name": supply.name}
                            for prop in ["status", "capacity", "voltage_now", "current_now"]:
                                prop_file = supply / prop
                                if prop_file.exists():
                                    with open(prop_file) as pf:
                                        battery[prop] = pf.read().strip()
                            status["batteries"].append(battery)
                except IOError:
                    pass

    # Check thermal zones
    tz_base = Path("/sys/class/thermal")
    if tz_base.exists():
        for tz in sorted(tz_base.glob("thermal_zone*")):
            zone = {"name": tz.name}
            try:
                temp_file = tz / "temp"
                type_file = tz / "type"
                if temp_file.exists():
                    with open(temp_file) as f:
                        zone["temp_millicelsius"] = int(f.read().strip())
                        zone["temp_celsius"] = zone["temp_millicelsius"] / 1000
                if type_file.exists():
                    with open(type_file) as f:
                        zone["type"] = f.read().strip()
                status["thermal_zones"].append(zone)
            except (IOError, ValueError):
                pass

    return status


# Background logging task
_logging_task = None


async def start_background_logging():
    """Start the background logging task."""
    global _logging_task

    init_database()

    async def logging_loop():
        while True:
            try:
                log_current_metrics()
            except Exception as e:
                print(f"Error logging metrics: {e}")
            await asyncio.sleep(LOG_INTERVAL)

    _logging_task = asyncio.create_task(logging_loop())
    return _logging_task


def stop_background_logging():
    """Stop the background logging task."""
    global _logging_task
    if _logging_task:
        _logging_task.cancel()
        _logging_task = None
