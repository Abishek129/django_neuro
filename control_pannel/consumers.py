import json

from channels.generic.websocket import AsyncWebsocketConsumer

from neuro_backend.permissions import has_logger_read_role


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        claims = self.scope.get("auth") or {}
        if not claims:
            await self.close(code=4401)
            return

        user_uuid = (claims or {}).get("sub")
        if not user_uuid:
            await self.close(code=4401)
            return
        self.group_name = f"notifications_{user_uuid}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def notification_message(self, event):
        payload = event.get("payload", {})
        await self.send(text_data=json.dumps({"type": "notification", "notification": payload}))
