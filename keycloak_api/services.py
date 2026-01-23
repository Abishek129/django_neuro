import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple


def _settings() -> dict:
    return {
        "base_url": os.getenv("KEYCLOAK_BASE_URL", "http://127.0.0.1:8080"),
        "realm": os.getenv("KEYCLOAK_REALM", "desktop"),
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "webshell"),
        "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
        "admin_realm": os.getenv("KEYCLOAK_ADMIN_REALM", "master"),
        "admin_client_id": os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli"),
        "admin_username": os.getenv("KEYCLOAK_ADMIN_USERNAME"),
        "admin_password": os.getenv("KEYCLOAK_ADMIN_PASSWORD"),
    }


def _request(
    method: str,
    url: str,
    headers: Dict[str, str] | None = None,
    data: bytes | None = None,
) -> Tuple[int, Dict[str, Any] | None, Dict[str, str]]:
    req = urllib.request.Request(url, method=method)
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    if data is not None:
        req.data = data

    try:
        with urllib.request.urlopen(req, data=data) as resp:
            body = resp.read()
            parsed = None
            if body:
                try:
                    parsed = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    parsed = {"raw": body.decode("utf-8", errors="replace")}
            return resp.status, parsed, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read()
        parsed = None
        if body:
            try:
                parsed = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = {"raw": body.decode("utf-8", errors="replace")}
        return e.code, parsed, dict(e.headers)


def _form_post(url: str, payload: Dict[str, str]) -> Tuple[int, Dict[str, Any] | None, Dict[str, str]]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    return _request("POST", url, headers=headers, data=data)


def _json_post(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None):
    data = json.dumps(payload).encode("utf-8")
    base_headers = {"Content-Type": "application/json"}
    if headers:
        base_headers.update(headers)
    return _request("POST", url, headers=base_headers, data=data)


def _json_put(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None):
    data = json.dumps(payload).encode("utf-8")
    base_headers = {"Content-Type": "application/json"}
    if headers:
        base_headers.update(headers)
    return _request("PUT", url, headers=base_headers, data=data)


def login(username: str, password: str):
    cfg = _settings()
    token_url = f"{cfg['base_url']}/realms/{cfg['realm']}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": cfg["client_id"],
        "username": username,
        "password": password,
    }
    if cfg["client_secret"]:
        payload["client_secret"] = cfg["client_secret"]
    return _form_post(token_url, payload)


def _admin_token() -> tuple[str | None, dict | None, int | None]:
    cfg = _settings()
    if not cfg["admin_username"] or not cfg["admin_password"]:
        return None, {"detail": "Admin credentials not configured"}, 500
    token_url = f"{cfg['base_url']}/realms/{cfg['admin_realm']}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": cfg["admin_client_id"],
        "username": cfg["admin_username"],
        "password": cfg["admin_password"],
    }
    status, data, _ = _form_post(token_url, payload)
    if status != 200 or not data:
        return None, {
            "detail": "Admin token request failed",
            "status": status,
            "response": data,
            "token_url": token_url,
        }, status
    return data.get("access_token"), None, None


def register_user(username: str, password: str, email: str | None = None):
    token, error, status_code = _admin_token()
    if not token:
        return status_code or 500, error or {"detail": "Admin credentials not configured"}

    cfg = _settings()
    users_url = f"{cfg['base_url']}/admin/realms/{cfg['realm']}/users"
    payload: Dict[str, Any] = {
        "username": username,
        "enabled": True,
    }
    if email:
        payload["email"] = email
        payload["emailVerified"] = True

    status, data, headers = _json_post(
        users_url,
        payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if status not in (200, 201, 204):
        return status, data or {"detail": "Failed to create user"}

    location = headers.get("Location")
    if not location:
        return 500, {"detail": "User created but no Location header returned"}

    user_id = location.rstrip("/").split("/")[-1]
    password_url = f"{users_url}/{user_id}/reset-password"
    pw_payload = {
        "type": "password",
        "value": password,
        "temporary": False,
    }
    pw_status, pw_data, _ = _json_put(
        password_url,
        pw_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if pw_status not in (200, 204):
        return pw_status, pw_data or {"detail": "User created but failed to set password"}

    return 201, {"id": user_id, "username": username}
