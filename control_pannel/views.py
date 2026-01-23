from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from neuro_backend.http import parse_json

from . import services
from .models import Notification


def _notification_to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "message": notification.message,
        "read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


def _broadcast_notification(notification: Notification) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "notification.message",
            "payload": _notification_to_dict(notification),
        },
    )


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

    # Expect roles to include id and name at least. If only names are passed, reject to avoid ambiguities.
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
    payload, error = parse_json(request)
    if error:
        return error

    message = payload.get("message")
    if not message:
        return JsonResponse({"detail": "Missing message"}, status=400)

    read_value = payload.get("read", payload.get("is_read", False))
    notification = Notification.objects.create(
        message=message,
        is_read=bool(read_value),
    )
    _broadcast_notification(notification)
    return JsonResponse({"notification": _notification_to_dict(notification)}, status=201)


@csrf_exempt
@require_http_methods(["GET"])
def unread_notifications_count(request):
    count = Notification.objects.filter(is_read=False).count()
    return JsonResponse({"unread": count})


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
