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

        # Get active AP path to check which network is connected
        active_ap_path = None
        try:
            active_ap_path = wifi.ActiveAccessPoint
            if active_ap_path == "/":
                active_ap_path = None
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
            is_connected = active_ap_path is not None and ap_path == active_ap_path
            networks.append(
                {
                    "ssid": ssid,
                    "signal_strength": ap.Strength,
                    "security": security,
                    "is_open": security == "Open",
                    "is_connected": is_connected,
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

        # Get interface name (e.g., wlp33s0f4u1) instead of device path ID
        interface_name = device.Interface

        return {
            "ssid": ssid,
            "device": interface_name,
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
        # Return stdout on success, stderr on failure
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or result.stdout.strip()
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


def _delete_connection_profiles(ssid: str) -> bool:
    """Delete all connection profiles matching the SSID."""
    deleted = False

    # List all connections and find wireless ones matching this SSID
    list_success, output = _run_nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])
    if list_success and output:
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and "wireless" in parts[1].lower():
                conn_name = parts[0]
                # Match exact name or SSID contained in connection name
                if conn_name == ssid or ssid in conn_name or conn_name in ssid:
                    del_success, del_output = _run_nmcli(["connection", "delete", conn_name])
                    print(f"[WiFi] Delete '{conn_name}': {'OK' if del_success else del_output}")
                    if del_success:
                        deleted = True

    # Also try exact SSID delete (may have quotes or escaping)
    if not deleted:
        del_success, _ = _run_nmcli(["connection", "delete", ssid])
        if del_success:
            print(f"[WiFi] Deleted connection: {ssid}")
            deleted = True

    return deleted


def _connect_network_shell(ssid: str, password: Optional[str] = None) -> tuple[bool, str]:
    print(f"[WiFi] Connecting to: {ssid}")

    # Delete any existing profile for this SSID to avoid conflicts
    _delete_connection_profiles(ssid)

    # Create connection with proper security settings
    add_args = [
        "connection", "add",
        "type", "wifi",
        "con-name", ssid,
        "ssid", ssid,
    ]

    if password:
        add_args.extend([
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", password,
        ])

    print(f"[WiFi] Creating connection profile...")
    success, output = _run_nmcli(add_args)
    if not success:
        print(f"[WiFi] Failed to create profile: {output}")
        return False, output

    # Activate the connection
    print(f"[WiFi] Activating connection...")
    success, output = _run_nmcli(["connection", "up", ssid])
    if success:
        print(f"[WiFi] Connected to: {ssid}")
        return True, f"Connected to {ssid}"

    print(f"[WiFi] Activation failed: {output}")

    # Clean up on failure
    _run_nmcli(["connection", "delete", ssid])
    return False, output


def _disable_autoconnect_for_ssid(target_ssid: str):
    """Disable autoconnect on ALL profiles that connect to this SSID."""
    list_success, output = _run_nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])
    if not list_success or not output:
        return

    for line in output.split("\n"):
        parts = line.split(":")
        if len(parts) >= 2 and "wireless" in parts[1].lower():
            conn_name = parts[0]
            # Check if this profile connects to the target SSID
            ssid_success, ssid_output = _run_nmcli([
                "-t", "-f", "802-11-wireless.ssid",
                "connection", "show", conn_name
            ])
            if ssid_success and target_ssid in ssid_output:
                _run_nmcli(["connection", "modify", conn_name, "connection.autoconnect", "no"])
                print(f"[WiFi] Disabled autoconnect for: {conn_name}")


def _disconnect_shell() -> bool:
    current = _get_current_connection_shell()
    if current:
        device = current.get("device")
        if device:
            # Use device disconnect - this prevents auto-reconnect
            # (connection down would just reconnect immediately if autoconnect=yes)
            print(f"[WiFi] Disconnecting device: {device}")
            success, output = _run_nmcli(["device", "disconnect", device])
            print(f"[WiFi] Device disconnect result: {success}, {output}")
            return success
        else:
            # Fallback to connection down
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


# Security type mapping for model choices
SECURITY_MAP = {
    "WPA3": "wpa3",
    "WPA2": "wpa2",
    "WPA": "wpa",
    "WEP": "wep",
}


def _map_security_type(security: str) -> str:
    """Map raw security string to model choice."""
    for key, value in SECURITY_MAP.items():
        if key in security:
            return value
    return "open"


def get_security_type(ssid: str) -> str:
    """Get security type for an SSID from scan results."""
    networks = scan_networks()
    network = next((n for n in networks if n["ssid"] == ssid), None)
    if not network:
        return "wpa2"
    return _map_security_type(network.get("security", "Open"))


def get_current_signal_strength() -> int:
    """Get signal strength of current connection."""
    current = get_current_connection()
    return current.get("signal_strength", 0) if current else 0
