import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class KeycloakError(Exception):
    """Raised when a Keycloak admin request fails."""


class KeycloakClient:
    def __init__(self):
        self.base_url = getattr(settings, "KEYCLOAK_BASE_URL", os.getenv("KEYCLOAK_BASE_URL", "http://192.168.1.20:8080/keycloak"))
        self.admin_username = getattr(settings, "KEYCLOAK_ADMIN_USERNAME", os.getenv("KEYCLOAK_ADMIN_USERNAME"))
        self.admin_password = getattr(settings, "KEYCLOAK_ADMIN_PASSWORD", os.getenv("KEYCLOAK_ADMIN_PASSWORD"))
        self.client_id = getattr(settings, "KEYCLOAK_CLIENT_ID", os.getenv("KEYCLOAK_CLIENT_ID", "admin-cli"))

    def _token_endpoint(self) -> str:
        return f"{self.base_url}/realms/master/protocol/openid-connect/token"

    def _realm_admin_url(self, realm: str) -> str:
        return f"{self.base_url}/admin/realms/{realm}"

    def obtain_admin_token(self) -> str:
        if not self.admin_username or not self.admin_password:
            raise KeycloakError("Keycloak admin credentials are not configured")

        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": self.admin_username,
            "password": self.admin_password,
        }
        response = requests.post(self._token_endpoint(), data=data, timeout=10)
        if response.status_code != 200:
            log.error("Failed to obtain admin token: %s", response.text)
            raise KeycloakError("Failed to obtain admin token")

        token = response.json().get("access_token")
        if not token:
            raise KeycloakError("Admin token missing in response")
        return token

    def create_group(
        self,
        realm: str,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        payload: Dict[str, Any] = {"name": name}
        normalized_attributes: Dict[str, list[str]] | None = None
        if attributes:
            normalized_attributes = self._normalize_attributes(attributes)
            payload["attributes"] = normalized_attributes

        if parent_id:
            url = f"{self._realm_admin_url(realm)}/groups/{parent_id}/children"
        else:
            url = f"{self._realm_admin_url(realm)}/groups"

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 409:
            raise KeycloakError("Group already exists")
        if response.status_code != 201:
            log.error("Failed to create group (status %s): %s", response.status_code, response.text)
            raise KeycloakError("Failed to create group")

        group_id = self._extract_group_id(response)
        return {"id": group_id, "name": name, "attributes": normalized_attributes or {}, "parent_id": parent_id}

    def list_users(
        self,
        realm: str,
        search: Optional[str] = None,
        first: int = 0,
        max_results: int = 50,
    ) -> Any:
        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        if first:
            params["first"] = first
        if max_results:
            params["max"] = max_results

        url = f"{self._realm_admin_url(realm)}/users"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            log.error("Failed to list users (status %s): %s", response.status_code, response.text)
            raise KeycloakError("Failed to list users")
        return response.json()

    def list_realm_roles(
        self,
        realm: str,
        search: Optional[str] = None,
        first: int = 0,
        max_results: int = 100,
    ) -> Any:
        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}"}

        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        if first:
            params["first"] = first
        if max_results:
            params["max"] = max_results

        url = f"{self._realm_admin_url(realm)}/roles"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            log.error("Failed to list roles (status %s): %s", response.status_code, response.text)
            raise KeycloakError("Failed to list roles")
        return response.json()

    def find_user_id(self, realm: str, username: str) -> Optional[str]:
        try:
            users = self.list_users(realm=realm, search=username, first=0, max_results=10)
        except KeycloakError:
            return None
        for user in users or []:
            if user.get("username") == username:
                return user.get("id")
        if users:
            return users[0].get("id")
        return None

    def find_group_id(self, realm: str, group_name: str) -> Optional[str]:
        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {"search": group_name}
        url = f"{self._realm_admin_url(realm)}/groups"
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            log.error("Failed to search groups (status %s): %s", response.status_code, response.text)
            return None
        groups = response.json() or []
        for group in groups:
            if group.get("name") == group_name:
                return group.get("id")
        if groups:
            return groups[0].get("id")
        return None

    def add_user_to_group(
        self,
        realm: str,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        username: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> None:
        resolved_user_id = user_id or (self.find_user_id(realm, username) if username else None)
        if not resolved_user_id:
            raise KeycloakError("User not found")

        resolved_group_id = group_id or (self.find_group_id(realm, group_name) if group_name else None)
        if not resolved_group_id:
            raise KeycloakError("Group not found")

        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self._realm_admin_url(realm)}/users/{resolved_user_id}/groups/{resolved_group_id}"
        response = requests.put(url, headers=headers, timeout=10)
        if response.status_code == 204:
            return
        if response.status_code == 404:
            raise KeycloakError("User or group not found")
        if response.status_code == 409:
            raise KeycloakError("User already in group")
        log.error("Failed to add user to group (status %s): %s", response.status_code, response.text)
        raise KeycloakError("Failed to add user to group")

    def add_roles_to_group(
        self,
        realm: str,
        group_id: str,
        roles: list[Dict[str, Any]],
    ) -> None:
        token = self.obtain_admin_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self._realm_admin_url(realm)}/groups/{group_id}/role-mappings/realm"
        response = requests.post(url, headers=headers, json=roles, timeout=10)
        if response.status_code == 204:
            return
        if response.status_code == 404:
            raise KeycloakError("Group or role not found")
        if response.status_code == 409:
            raise KeycloakError("Role already assigned to group")
        log.error("Failed to add roles to group (status %s): %s", response.status_code, response.text)
        raise KeycloakError("Failed to add roles to group")

    @staticmethod
    def _extract_group_id(response: requests.Response) -> Optional[str]:
        location = response.headers.get("Location")
        if not location:
            return None
        parts = [p for p in location.rstrip("/").split("/") if p]
        return parts[-1] if parts else None

    @staticmethod
    def _normalize_attributes(attributes: Dict[str, Any]) -> Dict[str, list[str]]:
        normalized: Dict[str, list[str]] = {}
        for key, value in attributes.items():
            if value is None:
                continue
            if isinstance(value, list):
                normalized[key] = [str(v) for v in value]
            else:
                normalized[key] = [str(value)]
        return normalized

def create_group(realm: str, name: str, attributes: Optional[Dict[str, Any]] = None, parent_id: Optional[str] = None) -> Dict[str, Any]:
    client = KeycloakClient()
    return client.create_group(realm, name, attributes, parent_id)


def list_users(realm: str, search: Optional[str] = None, first: int = 0, max_results: int = 50) -> Any:
    client = KeycloakClient()
    return client.list_users(realm, search=search, first=first, max_results=max_results)


def add_user_to_group(
    realm: str,
    user_id: Optional[str] = None,
    group_id: Optional[str] = None,
    username: Optional[str] = None,
    group_name: Optional[str] = None,
) -> None:
    client = KeycloakClient()
    return client.add_user_to_group(
        realm=realm,
        user_id=user_id,
        group_id=group_id,
        username=username,
        group_name=group_name,
    )


def list_realm_roles(realm: str, search: Optional[str] = None, first: int = 0, max_results: int = 100) -> Any:
    client = KeycloakClient()
    return client.list_realm_roles(realm=realm, search=search, first=first, max_results=max_results)


def add_roles_to_group(realm: str, group_id: str, roles: list[Dict[str, Any]]) -> None:
    client = KeycloakClient()
    return client.add_roles_to_group(realm=realm, group_id=group_id, roles=roles)
