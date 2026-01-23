from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from neuro_backend.http import parse_json

from . import services


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    payload, error = parse_json(request)
    if error:
        return error

    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return JsonResponse({"detail": "Missing username or password"}, status=400)

    status, data, _ = services.login(username, password)
    if status != 200:
        return JsonResponse(data or {"detail": "Login failed"}, status=status)
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    payload, error = parse_json(request)
    if error:
        return error

    username = payload.get("username")
    password = payload.get("password")
    email = payload.get("email")
    if not username or not password:
        return JsonResponse({"detail": "Missing username or password"}, status=400)

    status, data = services.register_user(username, password, email)
    return JsonResponse(data, status=status)


@csrf_exempt
@require_http_methods(["POST"])
def authenticate(request):
    return login(request)
