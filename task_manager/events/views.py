from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def get_events(request):
    metric = request.GET.get("metric")
    severity = request.GET.get("severity")
    limit = request.GET.get("limit", 50)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 50
    return JsonResponse(services.get_events(metric=metric, severity=severity, limit=limit))
