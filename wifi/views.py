from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from neuro_backend.http import parse_json

from . import services


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
    return JsonResponse({"enabled": bool(enabled), "success": True})


@csrf_exempt
@require_http_methods(["GET"])
def get_networks(request):
    return JsonResponse({"networks": services.scan_networks()})


@csrf_exempt
@require_http_methods(["GET"])
def get_current(request):
    return JsonResponse({"current": services.get_current_connection()})


@csrf_exempt
@require_http_methods(["POST"])
def connect(request):
    payload, error = parse_json(request)
    if error:
        return error

    ssid = payload.get("ssid")
    if not ssid:
        return JsonResponse({"detail": "Missing ssid"}, status=400)

    success, message = services.connect_to_network(ssid, payload.get("password"))
    if not success:
        return JsonResponse({"detail": message or "Failed to connect"}, status=500)
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
