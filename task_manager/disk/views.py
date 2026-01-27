from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def get_status(request):
    return JsonResponse(services.get_disk_status())


@csrf_exempt
@require_http_methods(["GET"])
def get_history(request):
    return JsonResponse(services.get_disk_history())


@csrf_exempt
@require_http_methods(["GET"])
def get_breakdown(request):
    return JsonResponse(services.get_disk_breakdown())


@csrf_exempt
@require_http_methods(["GET"])
def get_processes(request):
    limit = request.GET.get("limit", 20)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 20
    return JsonResponse(services.get_disk_processes(limit=limit))
