from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class Notification(models.Model):
    message = models.TextField()
    user_uuid = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.message[:50]}"


def notification_group_name(user_uuid: str) -> str:
    return f"notifications_{user_uuid}"


def _broadcast_notification_instance(notification: 'Notification') -> None:
    if not notification.user_uuid:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = {
        "id": notification.id,
        "message": notification.message,
        "user_uuid": str(notification.user_uuid),
        "read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }
    async_to_sync(channel_layer.group_send)(
        notification_group_name(str(notification.user_uuid)),
        {
            "type": "notification.message",
            "payload": payload,
        },
    )


@receiver(post_save, sender=Notification)
def _notify_on_create(sender, instance: 'Notification', created: bool, **kwargs):
    if not created:
        return
    transaction.on_commit(lambda: _broadcast_notification_instance(instance))
