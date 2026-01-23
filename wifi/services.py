"""
WiFi Service - Controls NetworkManager via D-Bus with shell fallback.
"""
import subprocess
from typing import Optional


def _get_dbus_connection():
    try:
        from dasbus.connection import SystemMessageBus
        return SystemMessageBus()
    except ImportError:
        return None


def _get_wifi_enabled_dbus() -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    nm = bus.get_proxy("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
    return nm.WirelessEnabled


def _set_wifi_enabled_dbus(enabled: bool) -> bool:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    nm = bus.get_proxy("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
    nm.WirelessEnabled = enabled
    return True


def _parse_security_flags(wpa_flags: int, rsn_flags: int) -> str:
    if rsn_flags & 0x200:
        return "WPA3"
    if rsn_flags & 0x100:
        return "WPA2"
    if wpa_flags & 0x100:
        return "WPA1"
    if wpa_flags & 0x1:
        return "WEP"
    return "Open"


def _get_networks_dbus() -> list[dict]:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    nm = bus.get_proxy("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")

    networks = []
    seen_ssids = set()

    for device_path in nm.GetDevices():
        device = bus.get_proxy("org.freedesktop.NetworkManager", device_path)
        if device.DeviceType != 2:
            continue

        wifi = bus.get_proxy("org.freedesktop.NetworkManager", device_path)
        try:
            wifi.RequestScan({})
        except Exception:
            pass

        for ap_path in wifi.GetAccessPoints():
            ap = bus.get_proxy("org.freedesktop.NetworkManager", ap_path)
            ssid_bytes = ap.Ssid
            if not ssid_bytes:
                continue

            ssid = bytes(ssid_bytes).decode("utf-8", errors="ignore")
            if not ssid or ssid in seen_ssids:
                continue
            seen_ssids.add(ssid)

            security = _parse_security_flags(ap.WpaFlags, ap.RsnFlags)
            networks.append(
                {
                    "ssid": ssid,
                    "signal_strength": ap.Strength,
                    "security": security,
                    "is_open": security == "Open",
                    "is_connected": False,
                }
            )

    networks.sort(key=lambda x: x["signal_strength"], reverse=True)
    return networks


def _get_current_connection_dbus() -> Optional[dict]:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    nm = bus.get_proxy("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")

    for device_path in nm.GetDevices():
        device = bus.get_proxy("org.freedesktop.NetworkManager", device_path)
        if device.DeviceType != 2:
            continue

        if device.State != 100:
            continue

        wifi = bus.get_proxy("org.freedesktop.NetworkManager", device_path)
        active_ap_path = wifi.ActiveAccessPoint
        if not active_ap_path or active_ap_path == "/":
            continue

        ap = bus.get_proxy("org.freedesktop.NetworkManager", active_ap_path)
        ssid = bytes(ap.Ssid).decode("utf-8", errors="ignore")
        security = _parse_security_flags(ap.WpaFlags, ap.RsnFlags)

        return {
            "ssid": ssid,
            "device": device_path.split("/")[-1],
            "signal_strength": ap.Strength,
            "security": security,
            "status": "Connected",
        }

    return None


def _run_nmcli(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["nmcli"] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def _get_wifi_enabled_shell() -> bool:
    success, output = _run_nmcli(["radio", "wifi"])
    return success and "enabled" in output.lower()


def _set_wifi_enabled_shell(enabled: bool) -> bool:
    state = "on" if enabled else "off"
    success, _ = _run_nmcli(["radio", "wifi", state])
    return success


def _get_networks_shell() -> list[dict]:
    _run_nmcli(["device", "wifi", "rescan"])

    success, output = _run_nmcli([
        "-t",
        "-f",
        "SSID,SIGNAL,SECURITY,IN-USE",
        "device",
        "wifi",
        "list",
    ])

    networks = []
    seen_ssids = set()

    if success and output:
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) >= 4:
                ssid = parts[0]
                if not ssid or ssid in seen_ssids:
                    continue
                seen_ssids.add(ssid)

                try:
                    signal = int(parts[1]) if parts[1] else 0
                except ValueError:
                    signal = 0

                security = parts[2] if parts[2] else "Open"
                is_connected = parts[3] == "*"

                networks.append(
                    {
                        "ssid": ssid,
                        "signal_strength": signal,
                        "security": security,
                        "is_open": security == "" or security.lower() == "open",
                        "is_connected": is_connected,
                    }
                )

    networks.sort(key=lambda x: x["signal_strength"], reverse=True)
    return networks


def _get_signal_strength_shell(device: str) -> int:
    success, output = _run_nmcli([
        "-t",
        "-f",
        "IN-USE,SIGNAL",
        "device",
        "wifi",
        "list",
        "ifname",
        device,
    ])
    if success and output:
        for line in output.split("\n"):
            if line.startswith("*"):
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
    return 0


def _get_security_type_shell(ssid: str) -> str:
    success, output = _run_nmcli(["-t", "-f", "SSID,SECURITY", "device", "wifi", "list"])
    if success and output:
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == ssid:
                return parts[1] if parts[1] else "Open"
    return "Unknown"


def _get_current_connection_shell() -> Optional[dict]:
    success, output = _run_nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])

    if success and output:
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and "wireless" in parts[1].lower():
                ssid = parts[0]
                device = parts[2]

                signal = _get_signal_strength_shell(device)
                security = _get_security_type_shell(ssid)

                return {
                    "ssid": ssid,
                    "device": device,
                    "signal_strength": signal,
                    "security": security,
                    "status": "Connected",
                }
    return None


def _connect_network_shell(ssid: str, password: Optional[str] = None) -> tuple[bool, str]:
    args = ["device", "wifi", "connect", ssid]
    if password:
        args.extend(["password", password])

    success, output = _run_nmcli(args)
    if success:
        return True, f"Connected to {ssid}"
    return False, output


def _disconnect_shell() -> bool:
    current = _get_current_connection_shell()
    if current:
        success, _ = _run_nmcli(["connection", "down", current["ssid"]])
        return success
    return True


def _forget_network_shell(ssid: str) -> bool:
    success, _ = _run_nmcli(["connection", "delete", ssid])
    return success


def get_wifi_enabled() -> bool:
    try:
        return _get_wifi_enabled_dbus()
    except Exception as e:
        print(f"[WiFi] DBus failed ({e}), using shell fallback")
        return _get_wifi_enabled_shell()


def set_wifi_enabled(enabled: bool) -> bool:
    try:
        return _set_wifi_enabled_dbus(enabled)
    except Exception as e:
        print(f"[WiFi] DBus failed ({e}), using shell fallback")
        return _set_wifi_enabled_shell(enabled)


def scan_networks() -> list[dict]:
    try:
        return _get_networks_dbus()
    except Exception as e:
        print(f"[WiFi] DBus failed ({e}), using shell fallback")
        return _get_networks_shell()


def get_current_connection() -> Optional[dict]:
    try:
        return _get_current_connection_dbus()
    except Exception as e:
        print(f"[WiFi] DBus failed ({e}), using shell fallback")
        return _get_current_connection_shell()


def connect_to_network(ssid: str, password: Optional[str] = None) -> tuple[bool, str]:
    return _connect_network_shell(ssid, password)


def disconnect() -> bool:
    return _disconnect_shell()


def forget_network(ssid: str) -> bool:
    return _forget_network_shell(ssid)


def get_wifi_status() -> dict:
    enabled = get_wifi_enabled()
    current = get_current_connection() if enabled else None
    networks = scan_networks() if enabled else []

    return {
        "enabled": enabled,
        "current_connection": current,
        "available_networks": networks,
    }
