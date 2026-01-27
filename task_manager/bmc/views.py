from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def get_status(request):
    return JsonResponse(services.get_bmc_status())


@csrf_exempt
@require_http_methods(["GET"])
def get_history(request):
    return JsonResponse(services.get_bmc_history())


@csrf_exempt
@require_http_methods(["GET"])
def get_sensors(request):
    return JsonResponse(services.get_bmc_sensors())


@csrf_exempt
@require_http_methods(["GET"])
def get_sel(request):
    limit = request.GET.get("limit", 50)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 50
    return JsonResponse(services.get_bmc_sel(limit=limit))
