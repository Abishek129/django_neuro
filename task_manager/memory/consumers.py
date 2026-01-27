import asyncio
import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer

from . import services


class MemoryMonitorConsumer(AsyncWebsocketConsumer):
    channel_layer_alias = "task_manager"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming_task = None
        self.interval = 2

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        interval_param = params.get("interval", [None])[0]
        if interval_param:
            try:
                self.interval = max(1, min(60, float(interval_param)))
            except (ValueError, TypeError):
                pass

        await self.accept()
        self.streaming_task = asyncio.create_task(self._stream_loop())

    async def disconnect(self, close_code):
        if self.streaming_task:
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if message.get("type") == "set_interval":
            new_interval = message.get("interval")
            if new_interval is not None:
                try:
                    self.interval = max(1, min(60, float(new_interval)))
                except (ValueError, TypeError):
                    pass

    async def _stream_loop(self):
        try:
            while True:
                data = await asyncio.to_thread(services.get_memory_status)
                await self.send(text_data=json.dumps({
                    "type": "memory_status",
                    "data": data,
                }))
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            return
