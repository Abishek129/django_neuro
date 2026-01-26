import base64
import json
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any] | None, str | None]:
    parts = token.split(".")
    if len(parts) != 3:
        return None, "Invalid token format"
    try:
        payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None, "Invalid token payload"
    return payload, None


def _extract_token(scope) -> str | None:
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token

    qs = parse_qs(scope.get("query_string", b"").decode())
    token = (qs.get("token") or [None])[0]
    return token


class KeycloakJwtWsMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token = _extract_token(scope)
        if token:
            claims, _ = _decode_jwt_no_verify(token)
            scope["auth"] = claims
        else:
            scope["auth"] = None

        return await self.inner(scope, receive, send)


def KeycloakJwtWsMiddlewareStack(inner):
    return KeycloakJwtWsMiddleware(inner)
