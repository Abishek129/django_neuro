import jwt
from jwt import PyJWKClient
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class KeycloakJWTAuthentication(BaseAuthentication):
    """
    Reads Authorization: Bearer <token>
    Verifies signature using Keycloak JWKS
    Puts claims into request.auth
    """

    def __init__(self):
        jwks_url = (
            f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/certs"
        )
        self.jwks_client = PyJWKClient(jwks_url)

    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None

        token = auth.split(" ", 1)[1].strip()
        if not token:
            raise AuthenticationFailed("Empty bearer token")

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=f"{settings.KEYCLOAK_BASE_URL.rstrip('/')}/realms/{settings.KEYCLOAK_REALM}",
                options={
                    "verify_aud": False,
                },
            )
        except Exception as e:
            raise AuthenticationFailed(f"Invalid token: {e}")

        return (None, claims)
