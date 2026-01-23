from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from neuro_backend.http import parse_json
from neuro_backend.permissions import ProjectManagerPermission

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def get_status(request):
    return JsonResponse(services.get_sound_status())


@csrf_exempt
@require_http_methods(["GET", "POST"])
def volume(request):
    if request.method == "GET":
        return JsonResponse({"volume": services.get_volume()})

    permission = ProjectManagerPermission()
    if not permission.has_permission(request):
        return permission.deny()
    print("===========True==========", permission)
    payload, error = parse_json(request)
    if error:
        return error

    volume_value = payload.get("volume")
    if volume_value is None:
        return JsonResponse({"detail": "Missing volume"}, status=400)

    success = services.set_volume(int(volume_value))
    if not success:
        return JsonResponse({"detail": "Failed to set volume"}, status=500)
    return JsonResponse({"volume": int(volume_value), "success": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mute(request):
    if request.method == "GET":
        return JsonResponse({"muted": services.get_mute()})

    payload, error = parse_json(request)
    if error:
        return error

    muted = payload.get("muted")
    if muted is None:
        return JsonResponse({"detail": "Missing muted"}, status=400)

    success = services.set_mute(bool(muted))
    if not success:
        return JsonResponse({"detail": "Failed to set mute"}, status=500)
    return JsonResponse({"muted": bool(muted), "success": True})


@csrf_exempt
@require_http_methods(["POST"])
def toggle_mute(request):
    success = services.toggle_mute()
    if not success:
        return JsonResponse({"detail": "Failed to toggle mute"}, status=500)
    return JsonResponse({"muted": services.get_mute(), "success": True})


@csrf_exempt
@require_http_methods(["GET"])
def get_devices(request):
    return JsonResponse({"devices": services.get_output_devices()})


@csrf_exempt
@require_http_methods(["POST"])
def set_device(request):
    payload, error = parse_json(request)
    if error:
        return error

    device_name = payload.get("device_name")
    if not device_name:
        return JsonResponse({"detail": "Missing device_name"}, status=400)

    success = services.set_default_sink(device_name)
    if not success:
        return JsonResponse({"detail": "Failed to set device"}, status=500)
    return JsonResponse({"device": device_name, "success": True})
