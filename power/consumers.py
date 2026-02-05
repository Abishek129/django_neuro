import json

from channels.generic.websocket import AsyncWebsocketConsumer


class PowerConsumer(AsyncWebsocketConsumer):
    group_name = "power_updates"

    async def connect(self):
        claims = self.scope.get("auth") or {}
        if not claims:
            await self.close(code=4401)
            return

        roles = (claims.get("realm_access") or {}).get("roles", [])
        if "power_to_shut" not in roles:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def power_message(self, event):
        payload = event.get("payload", {})
        await self.send(text_data=json.dumps({"type": "power", "data": payload}))
