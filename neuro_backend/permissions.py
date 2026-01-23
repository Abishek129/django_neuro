import base64
import json
from typing import Any, Dict, Tuple

from django.http import JsonResponse


class BasePermission:
    message = "Permission denied"
    status_code = 403

    def has_permission(self, request) -> bool:
        return True

    def deny(self) -> JsonResponse:
        return JsonResponse({"detail": self.message}, status=self.status_code)


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


class KeycloakGroupPermission(BasePermission):
    def __init__(self, group_name: str):
        self.group_name = group_name
        self.message = f"Missing required group: {group_name}"

    def has_permission(self, request) -> bool:
        token, error = _get_bearer_token(request)
        if error:
            try:
                self.message = json.loads(error.content.decode("utf-8")).get("detail", self.message)
            except (ValueError, json.JSONDecodeError):
                self.message = error.content.decode("utf-8")
            self.status_code = error.status_code
            return False

        payload, error = _decode_jwt_no_verify(token)
        if error:
            try:
                self.message = json.loads(error.content.decode("utf-8")).get("detail", self.message)
            except (ValueError, json.JSONDecodeError):
                self.message = error.content.decode("utf-8")
            self.status_code = error.status_code
            return False

        groups = payload.get("groups", [])
        if isinstance(groups, str):
            groups = [groups]
        if not isinstance(groups, list):
            self.message = "Invalid groups claim"
            return False

        if self.group_name not in groups and f"/{self.group_name}" not in groups:
            return False
        return True


class ProjectManagerPermission(KeycloakGroupPermission):
    def __init__(self):
        super().__init__("ProjectManager1")
