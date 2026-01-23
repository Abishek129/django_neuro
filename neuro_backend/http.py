import json
from django.http import JsonResponse


def parse_json(request):
    if not request.body:
        return {}, None
    try:
        return json.loads(request.body.decode("utf-8")), None
    except json.JSONDecodeError:
        return None, JsonResponse({"detail": "Invalid JSON"}, status=400)
