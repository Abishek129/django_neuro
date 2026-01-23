from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import services


@csrf_exempt
@require_http_methods(["GET"])
def list_sessions(request):
    return JsonResponse({"sessions": services.list_sessions()})


@csrf_exempt
@require_http_methods(["GET"])
def websocket_placeholder(request):
    return JsonResponse({"detail": "WebSocket endpoint. Use ws:// for /api/terminal/ws."}, status=426)
