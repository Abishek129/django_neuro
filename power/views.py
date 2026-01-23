from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def get_status(request):
    return JsonResponse(services.get_power_status())


@csrf_exempt
@require_http_methods(["POST"])
def authenticate(request):
    return JsonResponse({"detail": "Authentication not implemented"}, status=501)


@csrf_exempt
@require_http_methods(["POST"])
def sleep(request):
    success = services.sleep_system()
    if not success:
        return JsonResponse({"detail": "Failed to sleep"}, status=500)
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def restart(request):
    success = services.restart_system()
    if not success:
        return JsonResponse({"detail": "Failed to restart"}, status=500)
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def shutdown(request):
    success = services.shutdown_system()
    if not success:
        return JsonResponse({"detail": "Failed to shutdown"}, status=500)
    return JsonResponse({"success": True})
