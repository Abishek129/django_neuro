from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from neuro_backend.http import parse_json

from . import services
from .models import Device


def _device_to_dict(device: Device) -> dict:
    return {
        "id": device.device_id,
        "physical_key": device.physical_key,
        "name": device.name,
        "type": device.device_type,
        "connection": device.connection,
        "mac_address": device.mac_address,
        "is_connected": device.is_connected,
        "metadata": device.metadata,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
    }


def _get_device_from_payload(payload: dict):
    device_id = payload.get("device_id") or payload.get("id")
    mac_address = payload.get("mac_address")

    if device_id:
        return Device.objects.filter(device_id=device_id).first()
    if mac_address:
        return Device.objects.filter(mac_address=mac_address).first()
    return None


def _resolve_mac_address(payload: dict) -> str | None:
    mac_address = payload.get("mac_address")
    if mac_address:
        return mac_address

    device_id = payload.get("device_id") or payload.get("id")
    if device_id:
        return device_id
    return None


def _upsert_device(device_data: dict) -> Device:
    device_id = device_data.get("id")
    mac_address = device_data.get("mac_address")
    physical_key = device_data.get("physical_key")
    interfaces = device_data.get("interfaces") or []

    defaults = {
        "name": device_data.get("name", ""),
        "device_type": device_data.get("type", ""),
        "connection": device_data.get("connection", ""),
        "mac_address": mac_address,
        "is_connected": device_data.get("is_connected", True),
        "physical_key": physical_key,
        "metadata": {},
        "last_seen_at": timezone.now(),
    }

    metadata = {
        key: value
        for key, value in device_data.items()
        if key
        not in {
            "id",
            "name",
            "type",
            "connection",
            "mac_address",
            "is_connected",
            "physical_key",
        }
    }
    defaults["metadata"] = metadata

    device, _ = Device.objects.update_or_create(
        device_id=device_id,
        defaults=defaults,
    )
    if physical_key:
        Device.objects.filter(physical_key=physical_key).exclude(device_id=device.device_id).delete()
    if physical_key and interfaces:
        Device.objects.filter(physical_key__isnull=True, name__in=interfaces).delete()
    return device


@csrf_exempt
@require_http_methods(["GET"])
def get_devices(request):
    live = services.get_all_devices()
    seen_ids: set[str] = set()

    for device_data in live.get("connected_devices", []):
        device = _upsert_device(device_data)
        seen_ids.add(device.device_id)

    if seen_ids:
        Device.objects.exclude(device_id__in=seen_ids).update(
            is_connected=False,
            last_seen_at=timezone.now(),
        )

    devices = [_device_to_dict(device) for device in Device.objects.all()]
    connected = sum(1 for device in devices if device["is_connected"])
    return JsonResponse(
        {
            "devices": devices,
            "available_bluetooth": live.get("available_bluetooth", []),
            "counts": {
                "total": len(devices),
                "connected": connected,
                "disconnected": len(devices) - connected,
            },
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def scan_bluetooth(request):
    return JsonResponse({"devices": services.scan_bluetooth_devices()})


@csrf_exempt
@require_http_methods(["POST"])
def connect_bluetooth(request):
    payload, error = parse_json(request)
    if error:
        return error

    mac_address = _resolve_mac_address(payload)
    if not mac_address:
        return JsonResponse({"detail": "Missing mac_address"}, status=400)

    success, message = services.connect_bluetooth_device(mac_address)
    if not success:
        return JsonResponse({"detail": message or "Failed to connect"}, status=500)

    device = _get_device_from_payload(payload)
    if device:
        device.is_connected = True
        device.last_seen_at = timezone.now()
        device.save(update_fields=["is_connected", "last_seen_at"])
        return JsonResponse({"success": True, "device": _device_to_dict(device)})

    return JsonResponse({"success": True, "message": message})


@csrf_exempt
@require_http_methods(["POST"])
def disconnect_bluetooth(request):
    payload, error = parse_json(request)
    if error:
        return error

    mac_address = _resolve_mac_address(payload)
    if not mac_address:
        return JsonResponse({"detail": "Missing mac_address"}, status=400)

    success, message = services.disconnect_bluetooth_device(mac_address)
    if not success:
        return JsonResponse({"detail": message or "Failed to disconnect"}, status=500)

    device = _get_device_from_payload(payload)
    if device:
        device.is_connected = False
        device.last_seen_at = timezone.now()
        device.save(update_fields=["is_connected", "last_seen_at"])
        return JsonResponse({"success": True, "device": _device_to_dict(device)})

    return JsonResponse({"success": True, "message": message})


@csrf_exempt
@require_http_methods(["POST"])
def forget_bluetooth(request):
    payload, error = parse_json(request)
    if error:
        return error

    mac_address = _resolve_mac_address(payload)
    if not mac_address:
        return JsonResponse({"detail": "Missing mac_address"}, status=400)

    success, message = services.forget_bluetooth_device(mac_address)
    if not success:
        return JsonResponse({"detail": message or "Failed to remove device"}, status=500)

    device = _get_device_from_payload(payload)
    if device:
        device.delete()
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def forget_device(request):
    return forget_bluetooth(request)
