"""
Power Service - System power management via D-Bus with shell fallback.
"""
import subprocess


def _get_dbus_connection():
    try:
        from dasbus.connection import SystemMessageBus
        return SystemMessageBus()
    except ImportError:
        return None


def _sleep_system_dbus() -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    logind = bus.get_proxy("org.freedesktop.login1", "/org/freedesktop/login1")
    logind.Suspend(False)
    return True


def _restart_system_dbus() -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    logind = bus.get_proxy("org.freedesktop.login1", "/org/freedesktop/login1")
    logind.Reboot(False)
    return True


def _shutdown_system_dbus() -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    logind = bus.get_proxy("org.freedesktop.login1", "/org/freedesktop/login1")
    logind.PowerOff(False)
    return True


def _can_power_action_dbus(action: str) -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    logind = bus.get_proxy("org.freedesktop.login1", "/org/freedesktop/login1")

    if action == "sleep":
        result = logind.CanSuspend()
    elif action == "restart":
        result = logind.CanReboot()
    elif action == "shutdown":
        result = logind.CanPowerOff()
    else:
        return False

    return result in ("yes", "challenge")


def _run_systemctl(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["systemctl"] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def _sleep_system_shell() -> bool:
    success, _ = _run_systemctl(["suspend"])
    return success


def _restart_system_shell() -> bool:
    success, _ = _run_systemctl(["reboot"])
    return success


def _shutdown_system_shell() -> bool:
    success, _ = _run_systemctl(["poweroff"])
    return success


def sleep_system() -> bool:
    try:
        return _sleep_system_dbus()
    except Exception as e:
        print(f"[Power] DBus failed ({e}), using shell fallback")
        return _sleep_system_shell()


def restart_system() -> bool:
    try:
        return _restart_system_dbus()
    except Exception as e:
        print(f"[Power] DBus failed ({e}), using shell fallback")
        return _restart_system_shell()


def shutdown_system() -> bool:
    try:
        return _shutdown_system_dbus()
    except Exception as e:
        print(f"[Power] DBus failed ({e}), using shell fallback")
        return _shutdown_system_shell()


def can_power_action(action: str) -> bool:
    try:
        return _can_power_action_dbus(action)
    except Exception:
        return True


def get_power_status() -> dict:
    status = {
        "uptime": None,
        "load_average": None,
        "can_sleep": can_power_action("sleep"),
        "can_restart": can_power_action("restart"),
        "can_shutdown": can_power_action("shutdown"),
    }

    try:
        result = subprocess.run(
            ["uptime", "-p"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            status["uptime"] = result.stdout.strip()
    except Exception:
        pass

    try:
        with open("/proc/loadavg", "r") as f:
            load = f.read().strip().split()[:3]
            status["load_average"] = load
    except Exception:
        pass

    return status
