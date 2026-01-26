from asgiref.sync import async_to_sync
from datetime import datetime, timezone
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from neuro_backend.http import parse_json
from neuro_backend.permissions import HasLoggerReadRole, HasLoggerWriteRole, _get_token_claims

from . import services
from .models import Notification


def _notification_to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "message": notification.message,
        "user_uuid": str(notification.user_uuid) if notification.user_uuid else None,
        "read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


def _broadcast_notification(payload: dict) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "notification.message",
            "payload": payload,
        },
    )


def send_message_to_user(user_uuid: str, message: dict) -> bool:
    """Send a message to a specific user's WebSocket connection.

    Args:
        user_uuid: The user's UUID.
        message: The message payload to send.

    Returns:
        True if the message was sent, False if channel layer unavailable.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return False
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_uuid}",
        {
            "type": "notification.message",
            "payload": message,
        },
    )
    return True


@csrf_exempt
@require_http_methods(["POST"])
def test_websocket_message(request):
    """Test endpoint to send a message to a user's WebSocket."""
    payload, error = parse_json(request)
    if error:
        return error

    user_uuid = payload.get("user_uuid")
    message = payload.get("message")

    if not user_uuid:
        return JsonResponse({"detail": "Missing user_uuid"}, status=400)
    if not message:
        return JsonResponse({"detail": "Missing message"}, status=400)

    sent = send_message_to_user(user_uuid, message)
    return JsonResponse({"sent": sent, "user_uuid": user_uuid}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def create_group(request):
    payload, error = parse_json(request)
    if error:
        return error

    realm = payload.get("realm")
    name = payload.get("name")
    attributes = payload.get("attributes") or {}
    parent_id = payload.get("parent_id")

    if not realm or not name:
        return JsonResponse({"detail": "Missing realm or name"}, status=400)

    try:
        group = services.create_group(realm=realm, name=name, attributes=attributes, parent_id=parent_id)
    except services.KeycloakError as exc:
        message = str(exc)
        status_code = 409 if "exists" in message.lower() else 502
        return JsonResponse({"detail": message}, status=status_code)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while creating group"}, status=500)

    return JsonResponse({"group": group}, status=201)


@require_http_methods(["GET"])
def list_users(request):
    realm = request.GET.get("realm")
    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)

    search = request.GET.get("search")
    first = _parse_int(request.GET.get("first"), 0)
    max_results = _parse_int(request.GET.get("max"), 50)

    try:
        users = services.list_users(realm=realm, search=search, first=first, max_results=max_results)
    except services.KeycloakError as exc:
        return JsonResponse({"detail": str(exc)}, status=502)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while listing users"}, status=500)

    return JsonResponse({"users": users}, status=200, safe=False)


@require_http_methods(["GET"])
def list_roles(request):
    realm = request.GET.get("realm")
    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)

    search = request.GET.get("search")
    first = _parse_int(request.GET.get("first"), 0)
    max_results = _parse_int(request.GET.get("max"), 100)

    try:
        roles = services.list_realm_roles(realm=realm, search=search, first=first, max_results=max_results)
    except services.KeycloakError as exc:
        return JsonResponse({"detail": str(exc)}, status=502)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while listing roles"}, status=500)

    return JsonResponse({"roles": roles}, status=200, safe=False)


@require_http_methods(["GET"])
def list_users_by_roles(request):
    perm = HasLoggerReadRole()
    if not perm.has_permission(request):
        return perm.deny()

    realm = request.GET.get("realm")
    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)

    roles = request.GET.getlist("roles")
    if len(roles) == 1 and "," in roles[0]:
        roles = [r.strip() for r in roles[0].split(",") if r.strip()]

    if not roles:
        return JsonResponse({"detail": "Missing roles"}, status=400)

    users_by_id = {}
    for role in roles:
        try:
            role_users = services.list_role_users(realm=realm, role_name=role)
        except services.KeycloakError as exc:
            return JsonResponse({"detail": str(exc)}, status=502)
        except Exception:
            return JsonResponse({"detail": "Unexpected error while listing role users"}, status=500)

        for user in role_users or []:
            uid = user.get("id")
            if not uid:
                continue
            entry = users_by_id.setdefault(
                uid,
                {
                    "id": uid,
                    "username": user.get("username"),
                    "email": user.get("email"),
                    "firstName": user.get("firstName"),
                    "lastName": user.get("lastName"),
                    "enabled": user.get("enabled"),
                    "roles": [],
                },
            )
            if role not in entry["roles"]:
                entry["roles"].append(role)

    return JsonResponse({"roles": roles, "users": list(users_by_id.values())}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def add_user_to_group(request):
    payload, error = parse_json(request)
    if error:
        return error

    realm = payload.get("realm")
    user_id = payload.get("user_id")
    group_id = payload.get("group_id")
    username = payload.get("username")
    group_name = payload.get("group_name")

    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)
    if not (user_id or username):
        return JsonResponse({"detail": "Missing user_id or username"}, status=400)
    if not (group_id or group_name):
        return JsonResponse({"detail": "Missing group_id or group_name"}, status=400)

    try:
        services.add_user_to_group(
            realm=realm,
            user_id=user_id,
            group_id=group_id,
            username=username,
            group_name=group_name,
        )
    except services.KeycloakError as exc:
        message = str(exc)
        status_code = 409 if "already" in message.lower() else 404 if "not found" in message.lower() else 502
        return JsonResponse({"detail": message}, status=status_code)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while adding user to group"}, status=500)

    return JsonResponse({"success": True}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def add_roles_to_group(request):
    payload, error = parse_json(request)
    if error:
        return error

    realm = payload.get("realm")
    group_id = payload.get("group_id")
    roles = payload.get("roles") or []

    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)
    if not group_id:
        return JsonResponse({"detail": "Missing group_id"}, status=400)
    if not isinstance(roles, list) or not roles:
        return JsonResponse({"detail": "Missing roles"}, status=400)

    cleaned_roles = []
    for role in roles:
        if not isinstance(role, dict) or not role.get("id") or not role.get("name"):
            return JsonResponse({"detail": "Each role must include id and name"}, status=400)
        cleaned_roles.append({"id": role["id"], "name": role["name"]})

    try:
        services.add_roles_to_group(realm=realm, group_id=group_id, roles=cleaned_roles)
    except services.KeycloakError as exc:
        message = str(exc)
        status_code = 409 if "already" in message.lower() else 404 if "not found" in message.lower() else 502
        return JsonResponse({"detail": message}, status=status_code)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while adding roles to group"}, status=500)

    return JsonResponse({"success": True}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def create_notification(request):
    perm = HasLoggerWriteRole()
    if not perm.has_permission(request):
        return perm.deny()

    claims, error = _get_token_claims(request)
    if error:
        return error
    actor_uuid = (claims or {}).get("sub")
    if not actor_uuid:
        return JsonResponse({"detail": "User id not found in token"}, status=400)

    payload, error = parse_json(request)
    if error:
        return error

    message = payload.get("message")
    if not message:
        return JsonResponse({"detail": "Missing message"}, status=400)

    realm = payload.get("realm") or request.GET.get("realm")
    if not realm:
        return JsonResponse({"detail": "Missing realm"}, status=400)

    roles = payload.get("roles") or payload.get("role") or ["logger_read"]
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(",") if r.strip()]
    if not isinstance(roles, list) or not roles:
        return JsonResponse({"detail": "Missing roles"}, status=400)

    try:
        groups = services.list_groups(realm=realm, first=0, max_results=200)
        
    except services.KeycloakError as exc:
        return JsonResponse({"detail": str(exc)}, status=502)
    except Exception:
        return JsonResponse({"detail": "Unexpected error while listing groups"}, status=500)

    flat_groups = services.flatten_groups(groups)
    matched_groups = []
    for group in flat_groups:
        gid = group.get("id")
        if not gid:
            continue
        try:
            mappings = services.list_group_role_mappings(realm=realm, group_id=gid)
        except services.KeycloakError as exc:
            return JsonResponse({"detail": str(exc)}, status=502)
        except Exception:
            return JsonResponse({"detail": "Unexpected error while listing group roles"}, status=500)

        role_names = [m.get("name") for m in (mappings or []) if isinstance(m, dict)]
        if any(r in role_names for r in roles):
            matched_groups.append(group)

    if not matched_groups:
        return JsonResponse({"detail": "No groups found for requested roles"}, status=404)

    recipients = {}
    for group in matched_groups:
        gid = group.get("id")
        if not gid:
            continue
        try:
            members = services.list_group_members(realm=realm, group_id=gid, first=0, max_results=200)
        except services.KeycloakError as exc:
            return JsonResponse({"detail": str(exc)}, status=502)
        except Exception:
            return JsonResponse({"detail": "Unexpected error while listing group members"}, status=500)

        for user in members or []:
            uid = user.get("id")
            if not uid:
                continue
            recipients[uid] = {
                "id": uid,
                "username": user.get("username"),
                "email": user.get("email"),
                "firstName": user.get("firstName"),
                "lastName": user.get("lastName"),
                "enabled": user.get("enabled"),
            }

    if not recipients:
        return JsonResponse({"detail": "No users found in matched groups"}, status=404)

    read_value = payload.get("read", payload.get("is_read", False))
    created = []
    for uid in recipients.keys():
        notification = Notification.objects.create(
            message=message,
            user_uuid=uid,
            is_read=bool(read_value),
        )
        created.append(notification)

    # per-user broadcast handled in model signal

    return JsonResponse(
        {
            "created": len(created),
            "roles": roles,
            "recipients": list(recipients.values()),
        },
        status=201,
    )
