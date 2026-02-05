import jwt
from jwt import PyJWKClient
from urllib.parse import parse_qs
from django.conf import settings


class KeycloakJwtWsMiddleware:
    def __init__(self, inner):
        self.inner = inner
        jwks_url = (
            f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/certs"
        )
        self.jwks_client = PyJWKClient(jwks_url)

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        token = _extract_token(scope)
        if token:
            try:
                signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
                claims = jwt.decode(
                    token,
                    signing_key,
                    algorithms=["RS256"],
                    issuer=f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}",
                    options={"verify_aud": False},
                )
                scope["auth"] = claims
                scope["user"] = AnonymousUser()
            except Exception:
                scope["auth"] = None
                scope["user"] = AnonymousUser()
        else:
            scope["auth"] = None
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


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


def KeycloakJwtWsMiddlewareStack(inner):
    return KeycloakJwtWsMiddleware(inner)
