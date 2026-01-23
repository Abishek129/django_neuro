import base64
import json
from typing import Any, Dict, Tuple

from django.http import JsonResponse


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any] | None, JsonResponse | None]:
    parts = token.split(".")
    if len(parts) != 3:
        return None, JsonResponse({"detail": "Invalid token format"}, status=401)
    try:
        payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None, JsonResponse({"detail": "Invalid token payload"}, status=401)
    return payload, None


def _get_bearer_token(request) -> Tuple[str | None, JsonResponse | None]:
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
    if not auth_header:
        return None, JsonResponse({"detail": "Missing Authorization header"}, status=401)
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, JsonResponse({"detail": "Invalid Authorization header"}, status=401)
    return parts[1], None


def require_keycloak_group(request, group_name: str) -> JsonResponse | None:
    token, error = _get_bearer_token(request)
    if error:
        return error
    payload, error = _decode_jwt_no_verify(token)
    if error:
        return error

    groups = payload.get("groups", [])
    if isinstance(groups, str):
        groups = [groups]
    if not isinstance(groups, list):
        return JsonResponse({"detail": "Invalid groups claim"}, status=403)

    if group_name not in groups and f"/{group_name}" not in groups:
        return JsonResponse({"detail": f"Missing required group: {group_name}"}, status=403)
    return None
