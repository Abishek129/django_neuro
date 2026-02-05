from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from neuro_backend.http import parse_json

from . import services
from .models import SavedNetwork, ConnectionLog


@csrf_exempt
@require_http_methods(["GET"])
def get_status(request):
    return JsonResponse(services.get_wifi_status())


@csrf_exempt
@require_http_methods(["GET"])
def get_enabled(request):
    return JsonResponse({"enabled": services.get_wifi_enabled()})


@csrf_exempt
@require_http_methods(["POST"])
def toggle_wifi(request):
    payload, error = parse_json(request)
    if error:
        return error

    enabled = payload.get("enabled")
    if enabled is None:
        return JsonResponse({"detail": "Missing enabled"}, status=400)

    success = services.set_wifi_enabled(bool(enabled))
    if not success:
        return JsonResponse({"detail": "Failed to set WiFi"}, status=500)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "power_updates",
        {
            "type": "power.message",
            "payload": {"action": "wifi_toggle", "enabled": bool(enabled)},
        },
    )

    return JsonResponse({"enabled": bool(enabled), "success": True})


@csrf_exempt
@require_http_methods(["GET"])
def get_networks(request):
    return JsonResponse({"networks": services.scan_networks()})


@csrf_exempt
@require_http_methods(["GET"])
def get_current(request):
    return JsonResponse({"current": services.get_current_connection()})


def _save_network_on_success(ssid: str, password: str, security_type: str) -> SavedNetwork:
    """Save or update network after successful connection."""
    network, _ = SavedNetwork.objects.update_or_create(
        ssid=ssid,
        defaults={
            "security_type": security_type,
            "password": password or "",
            "auto_connect": True,
            "last_connected": timezone.now(),
        }
    )
    ConnectionLog.objects.create(
        network=network,
        event="connected",
        signal_strength=services.get_current_signal_strength(),
    )
    return network


def _log_connection_failure(ssid: str, error_message: str):
    """Log failed connection attempt if network exists."""
    network = SavedNetwork.objects.filter(ssid=ssid).first()
    if network:
        ConnectionLog.objects.create(network=network, event="failed", error_message=error_message)


@csrf_exempt
@require_http_methods(["POST"])
def connect(request):
    print("[WiFi Connect] Request received")
    payload, error = parse_json(request)
    if error:
        print("[WiFi Connect] JSON parse error")
        return error

    ssid = payload.get("ssid")
    if not ssid:
        print("[WiFi Connect] Missing SSID")
        return JsonResponse({"detail": "Missing ssid"}, status=400)

    password = payload.get("password")
    print(f"[WiFi Connect] Connecting to: {ssid}, password provided: {bool(password)}")

    success, message = services.connect_to_network(ssid, password)
    print(f"[WiFi Connect] nmcli result - success: {success}, message: {message}")

    if not success:
        print(f"[WiFi Connect] Connection FAILED: {message}")
        _log_connection_failure(ssid, message)
        return JsonResponse({"detail": message or "Failed to connect"}, status=500)

    print("[WiFi Connect] Connection successful, saving to database...")
    security_type = services.get_security_type(ssid)
    print(f"[WiFi Connect] Security type: {security_type}")
    _save_network_on_success(ssid, password, security_type)
    print("[WiFi Connect] Saved to database")
    return JsonResponse({"success": True, "message": message})


@csrf_exempt
@require_http_methods(["POST"])
def disconnect(request):
    success = services.disconnect()
    if not success:
        return JsonResponse({"detail": "Failed to disconnect"}, status=500)
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def forget(request):
    payload, error = parse_json(request)
    if error:
        return error

    ssid = payload.get("ssid")
    if not ssid:
        return JsonResponse({"detail": "Missing ssid"}, status=400)

    success = services.forget_network(ssid)
    if not success:
        return JsonResponse({"detail": "Failed to forget network"}, status=500)
    return JsonResponse({"success": True})


def _network_to_dict(network: SavedNetwork) -> dict:
    """Serialize SavedNetwork to dict."""
    return {
        "id": network.id,
        "ssid": network.ssid,
        "security_type": network.security_type,
        "auto_connect": network.auto_connect,
        "last_connected": network.last_connected.isoformat() if network.last_connected else None,
    }


def _get_network_by_id_or_ssid(network_id=None, ssid=None):
    """Fetch network by ID or SSID. Returns (network, error_response)."""
    if network_id:
        return SavedNetwork.objects.filter(id=network_id).first(), None
    if ssid:
        return SavedNetwork.objects.filter(ssid=ssid).first(), None
    return None, JsonResponse({"detail": "Missing network_id or ssid"}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
def get_saved_networks(request):
    """List all saved WiFi networks."""
    networks = SavedNetwork.objects.all()
    return JsonResponse({"saved_networks": [_network_to_dict(n) for n in networks]})


@csrf_exempt
@require_http_methods(["POST"])
def reconnect(request):
    """Reconnect to a saved network using stored password."""
    payload, error = parse_json(request)
    if error:
        return error

    network, error_response = _get_network_by_id_or_ssid(
        payload.get("network_id"),
        payload.get("ssid")
    )
    if error_response:
        return error_response
    if not network:
        return JsonResponse({"detail": "Network not found"}, status=404)

    success, message = services.connect_to_network(network.ssid, network.password)

    if not success:
        ConnectionLog.objects.create(network=network, event="failed", error_message=message)
        return JsonResponse({"detail": message}, status=500)

    network.last_connected = timezone.now()
    network.save(update_fields=["last_connected"])
    ConnectionLog.objects.create(network=network, event="connected")
    return JsonResponse({"success": True})
