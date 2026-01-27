import json

from channels.generic.websocket import AsyncWebsocketConsumer


class EventConsumer(AsyncWebsocketConsumer):
    channel_layer_alias = "task_manager"
    GROUP_NAME = "events"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def event_created(self, message):
        await self.send(text_data=json.dumps({
            "type": "event_created",
            "event": message["event"],
        }))
