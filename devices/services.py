"""
Devices Service - Detect connected Bluetooth, USB, and Input devices.

Architecture:
    API -> devices service -> DBus (Bluetooth) / Shell (USB, Input)
"""
import hashlib
import json
import re
import subprocess
from typing import Optional


def _run_command(args: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception:
        return False, ""


def _determine_device_type(name: str, icon: str = "") -> str:
    name_lower = name.lower()
    icon_lower = icon.lower()

    if any(x in name_lower for x in ["mouse", "trackpad", "touchpad"]):
        return "Mouse"
    if any(x in name_lower for x in ["keyboard", "keychron", "k2", "k3", "k6", "k8"]):
        return "Keyboard"
    if any(x in name_lower for x in ["headphone", "headset", "earphone", "earbud", "airpod", "buds", "wh-", "wf-"]):
        return "Headphones"
    if any(x in name_lower for x in ["speaker", "soundbar", "boombox"]):
        return "Speaker"
    if any(x in name_lower for x in ["controller", "gamepad", "xbox", "playstation", "dualsense"]):
        return "Controller"

    if "input-mouse" in icon_lower:
        return "Mouse"
    if "input-keyboard" in icon_lower:
        return "Keyboard"
    if "audio-headphones" in icon_lower or "audio-headset" in icon_lower:
        return "Headphones"
    if "audio-speakers" in icon_lower:
        return "Speaker"

    return "Bluetooth Device"


def _get_dbus_connection():
    try:
        from dasbus.connection import SystemMessageBus
        return SystemMessageBus()
    except ImportError:
        return None


def _get_bluetooth_devices_dbus() -> list[dict]:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    devices = []

    obj_manager = bus.get_proxy(
        "org.bluez",
        "/",
        "org.freedesktop.DBus.ObjectManager",
    )

    managed_objects = obj_manager.GetManagedObjects()

    for path, interfaces in managed_objects.items():
        if "org.bluez.Device1" not in interfaces:
            continue

        device_props = interfaces["org.bluez.Device1"]
        mac_address = device_props.get("Address", "")
        name = device_props.get("Name", device_props.get("Alias", "Unknown"))
        paired = device_props.get("Paired", False)
        connected = device_props.get("Connected", False)
        icon = device_props.get("Icon", "")

        if not paired:
            continue

        device_type = _determine_device_type(name, icon)
        battery = None
        if "org.bluez.Battery1" in interfaces:
            battery = interfaces["org.bluez.Battery1"].get("Percentage")

        devices.append(
            {
                "id": mac_address,
                "name": name,
                "type": device_type,
                "connection": "Bluetooth",
                "is_connected": connected,
                "mac_address": mac_address,
                "battery": battery,
            }
        )

    return devices


def _connect_bluetooth_dbus(mac_address: str) -> tuple[bool, str]:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    path = f"/org/bluez/hci0/dev_{mac_address.replace(':', '_')}"

    try:
        device = bus.get_proxy("org.bluez", path, "org.bluez.Device1")
        device.Connect()
        return True, f"Connected to {mac_address}"
    except Exception as e:
        return False, str(e)


def _disconnect_bluetooth_dbus(mac_address: str) -> tuple[bool, str]:
    bus = _get_dbus_connection()
    if not bus:
        raise Exception("DBus not available")

    path = f"/org/bluez/hci0/dev_{mac_address.replace(':', '_')}"

    try:
        device = bus.get_proxy("org.bluez", path, "org.bluez.Device1")
        device.Disconnect()
        return True, f"Disconnected from {mac_address}"
    except Exception as e:
        return False, str(e)


def _get_bluetooth_devices_shell() -> list[dict]:
    devices = []

    success, output = _run_command(["bluetoothctl", "devices", "Paired"])
    if not success or not output:
        return devices

    for line in output.split("\n"):
        if not line.startswith("Device "):
            continue

        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue

        mac_address = parts[1]
        name = parts[2]

        is_connected = _check_bluetooth_connected_shell(mac_address)
        info = _get_bluetooth_info_shell(mac_address)
        device_type = _determine_device_type(name, info.get("icon", ""))

        devices.append(
            {
                "id": mac_address,
                "name": name,
                "type": device_type,
                "connection": "Bluetooth",
                "is_connected": is_connected,
                "mac_address": mac_address,
                "battery": info.get("battery"),
            }
        )

    return devices


def _check_bluetooth_connected_shell(mac_address: str) -> bool:
    success, output = _run_command(["bluetoothctl", "info", mac_address])
    return success and "Connected: yes" in output


def _get_bluetooth_info_shell(mac_address: str) -> dict:
    info = {}
    success, output = _run_command(["bluetoothctl", "info", mac_address])

    if not success:
        return info

    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("Icon:"):
            info["icon"] = line.split(":", 1)[1].strip()
        elif line.startswith("Battery Percentage:"):
            match = re.search(r"\((\d+)\)", line)
            if match:
                info["battery"] = int(match.group(1))

    return info


def _connect_bluetooth_shell(mac_address: str) -> tuple[bool, str]:
    _run_command(["bluetoothctl", "pair", mac_address])
    _run_command(["bluetoothctl", "trust", mac_address])
    success, output = _run_command(["bluetoothctl", "connect", mac_address])

    if success or "Connection successful" in output:
        return True, f"Connected to {mac_address}"
    return False, output


def _disconnect_bluetooth_shell(mac_address: str) -> tuple[bool, str]:
    success, output = _run_command(["bluetoothctl", "disconnect", mac_address])
    if success:
        return True, f"Disconnected from {mac_address}"
    return False, output


def _forget_bluetooth_shell(mac_address: str) -> tuple[bool, str]:
    success, output = _run_command(["bluetoothctl", "remove", mac_address])
    if success:
        return True, f"Removed {mac_address}"
    return False, output


def _get_usb_devices() -> list[dict]:
    devices = []

    success, output = _run_command(
        ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,TRAN,VENDOR,MODEL,MOUNTPOINT,HOTPLUG"]
    )

    if not success:
        return devices

    try:
        data = json.loads(output)

        for device in data.get("blockdevices", []):
            if device.get("tran") != "usb" and device.get("hotplug") != "1":
                continue
            if device.get("type") not in ["disk", "part"]:
                continue

            vendor = (device.get("vendor") or "").strip() or "USB"
            model = (device.get("model") or "").strip() or "Storage"
            size = device.get("size", "")
            name = f"{vendor} {model}".strip()
            if size:
                name = f"{name} {size}"

            devices.append(
                {
                    "id": f"usb_{device.get('name', '')}",
                    "name": name,
                    "type": "USB Drive",
                    "connection": "USB",
                    "is_connected": True,
                    "size": size,
                }
            )

    except (json.JSONDecodeError, KeyError):
        pass

    return devices


_INPUT_TYPE_PRIORITY = {
    "Keyboard": 4,
    "Touchpad": 3,
    "Mouse": 2,
    "Input Device": 1,
}


def _determine_input_type(info: dict) -> str:
    handlers = (info.get("handlers") or "").lower()
    name_lower = (info.get("name") or "").lower()

    if info.get("has_rel") or "mouse" in handlers or "mouse" in name_lower:
        return "Mouse"
    if "kbd" in handlers or info.get("has_keys"):
        if "touchpad" in name_lower or info.get("has_abs"):
            return "Touchpad"
        return "Keyboard"
    return "Input Device"


def _determine_input_connection(info: dict) -> str:
    blob = f"{info.get('phys', '')} {info.get('sysfs', '')} {info.get('name', '')}".lower()
    return "USB" if "usb" in blob else "Built-in"


def _preferred_input_name(names: list[str]) -> str:
    for name in names:
        lower = name.lower()
        if "system control" not in lower and "consumer control" not in lower:
            return name
    if names:
        return min(names, key=len)
    return "Input Device"


def _normalize_phys(phys: str) -> str:
    if not phys or phys == "ALSA":
        return ""
    return re.sub(r"/input\d+$", "", phys)


def _usb_port_from_sysfs(sysfs: str) -> str:
    match = re.search(r"/usb\d+/([^/]+)", sysfs)
    if not match:
        return ""
    return match.group(1).split(":")[0]


def _physical_key_from_input(info: dict) -> str:
    phys = _normalize_phys(info.get("phys", ""))
    if phys:
        return f"phys:{phys}"

    sysfs = info.get("sysfs", "")
    if sysfs:
        usb_port = _usb_port_from_sysfs(sysfs)
        if usb_port:
            return f"usb:{usb_port}"
        base = re.sub(r"/input/input\d+$", "", sysfs)
        base = re.sub(r":\d+\.\d+", "", base)
        return f"sysfs:{base}"

    bus = info.get("bus", "")
    vendor = info.get("vendor", "")
    product = info.get("product", "")
    uniq = info.get("uniq", "")
    if bus or vendor or product or uniq:
        return f"id:{bus}:{vendor}:{product}:{uniq}"

    return f"name:{info.get('name', '')}"


def _input_device_id(physical_key: str, name: str) -> str:
    key = physical_key or name
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"input_{digest}"


def _get_input_devices() -> list[dict]:
    entries = []

    try:
        with open("/proc/bus/input/devices", "r") as f:
            content = f.read()

        for block in content.split("\n\n"):
            if not block.strip():
                continue

            device: dict = {}
            for line in block.split("\n"):
                if line.startswith("I: "):
                    for part in line[3:].split():
                        if "=" in part:
                            key, value = part.split("=", 1)
                            device[key.lower()] = value
                elif line.startswith("N: Name="):
                    device["name"] = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("P: Phys="):
                    device["phys"] = line.split("=", 1)[1].strip()
                elif line.startswith("S: Sysfs="):
                    device["sysfs"] = line.split("=", 1)[1].strip()
                elif line.startswith("U: Uniq="):
                    device["uniq"] = line.split("=", 1)[1].strip()
                elif line.startswith("H: Handlers="):
                    device["handlers"] = line.split("=", 1)[1]
                elif line.startswith("B: KEY="):
                    device["has_keys"] = True
                elif line.startswith("B: REL="):
                    device["has_rel"] = True
                elif line.startswith("B: ABS="):
                    device["has_abs"] = True

            name = device.get("name", "")

            skip_patterns = [
                "video bus",
                "power button",
                "lid switch",
                "sleep button",
                "pc speaker",
                "at translated",
                "virtual",
                "acpi",
                "bluetooth",
            ]
            if not name or any(x in name.lower() for x in skip_patterns):
                continue

            device["name"] = name
            entries.append(device)

    except Exception:
        return []

    grouped: dict[str, dict] = {}
    for entry in entries:
        physical_key = _physical_key_from_input(entry)
        device_type = _determine_input_type(entry)
        connection = _determine_input_connection(entry)
        name = entry.get("name", "")

        if physical_key in grouped:
            group = grouped[physical_key]
            group["interfaces"].append(name)
            current_type = group["type"]
            if _INPUT_TYPE_PRIORITY.get(device_type, 0) > _INPUT_TYPE_PRIORITY.get(current_type, 0):
                group["type"] = device_type
            if connection == "USB":
                group["connection"] = "USB"
            group["name"] = _preferred_input_name(group["interfaces"])
            continue

        grouped[physical_key] = {
            "id": _input_device_id(physical_key, name),
            "physical_key": physical_key,
            "name": name,
            "type": device_type,
            "connection": connection,
            "is_connected": True,
            "interfaces": [name],
        }

    devices = []
    for key, device in grouped.items():
        device["name"] = _preferred_input_name(device["interfaces"])
        devices.append(device)

    return devices


def get_bluetooth_devices() -> list[dict]:
    try:
        return _get_bluetooth_devices_dbus()
    except Exception as e:
        print(f"[Devices] DBus failed ({e}), using shell fallback")
        return _get_bluetooth_devices_shell()


def connect_bluetooth_device(mac_address: str) -> tuple[bool, str]:
    try:
        return _connect_bluetooth_dbus(mac_address)
    except Exception as e:
        print(f"[Devices] DBus failed ({e}), using shell fallback")
        return _connect_bluetooth_shell(mac_address)


def disconnect_bluetooth_device(mac_address: str) -> tuple[bool, str]:
    try:
        return _disconnect_bluetooth_dbus(mac_address)
    except Exception as e:
        print(f"[Devices] DBus failed ({e}), using shell fallback")
        return _disconnect_bluetooth_shell(mac_address)


def forget_bluetooth_device(mac_address: str) -> tuple[bool, str]:
    return _forget_bluetooth_shell(mac_address)


def scan_bluetooth_devices() -> list[dict]:
    import time

    _run_command(["bluetoothctl", "scan", "on"])
    time.sleep(3)
    _run_command(["bluetoothctl", "scan", "off"])

    devices = []
    success, output = _run_command(["bluetoothctl", "devices"])

    if not success:
        return devices

    paired_success, paired_output = _run_command(["bluetoothctl", "devices", "Paired"])
    paired_macs = set()
    if paired_success and paired_output:
        for line in paired_output.split("\n"):
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 2:
                    paired_macs.add(parts[1])

    for line in output.split("\n"):
        if not line.startswith("Device "):
            continue

        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue

        mac = parts[1]
        name = parts[2]

        if mac in paired_macs:
            continue

        device_type = _determine_device_type(name, "")
        devices.append({"id": mac, "name": name, "type": device_type, "mac_address": mac})

    return devices


def get_all_devices() -> dict:
    bluetooth_devices = get_bluetooth_devices()
    usb_devices = _get_usb_devices()
    input_devices = _get_input_devices()

    connected_bluetooth = [d for d in bluetooth_devices if d.get("is_connected")]
    available_bluetooth = [d for d in bluetooth_devices if not d.get("is_connected")]

    all_devices = list(connected_bluetooth)

    for d in usb_devices:
        all_devices.append(d)

    bt_names = {d["name"].lower() for d in bluetooth_devices}
    for inp in input_devices:
        if any(bt_name in inp["name"].lower() or inp["name"].lower() in bt_name for bt_name in bt_names):
            continue
        all_devices.append(inp)

    connected_count = sum(1 for d in all_devices if d.get("is_connected", True))
    disconnected_count = len(all_devices) - connected_count

    return {
        "connected_devices": all_devices,
        "available_bluetooth": available_bluetooth,
        "counts": {
            "bluetooth": len(connected_bluetooth),
            "usb": len(usb_devices),
            "input": len(input_devices),
            "total": len(all_devices),
            "connected": connected_count,
            "disconnected": disconnected_count,
        },
    }
