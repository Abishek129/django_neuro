import asyncio
import json
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer

from . import services


class TerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.reader_task = None

    async def connect(self):
        self.session_id = self.scope.get("url_route", {}).get("kwargs", {}).get("session_id")
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

        created = services.create_session(self.session_id)
        if not created:
            await self.close()
            return

        await self.accept()
        await self.send_json({"type": "session", "id": self.session_id})
        self.reader_task = asyncio.create_task(self._reader_loop())

    async def disconnect(self, close_code):
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        if self.session_id:
            services.close_session(self.session_id)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = message.get("type")
        if msg_type == "input":
            data = message.get("data", "")
            services.write_to_session(self.session_id, data)
        elif msg_type == "resize":
            rows = int(message.get("rows", 24))
            cols = int(message.get("cols", 80))
            services.resize_session(self.session_id, rows, cols)

    async def _reader_loop(self):
        try:
            while True:
                data = await asyncio.to_thread(services.read_from_session, self.session_id, 0.1)
                if data is None:
                    await self.send_json({"type": "exit", "message": "Shell exited"})
                    await self.close()
                    break
                if data:
                    await self.send_json({"type": "output", "data": data})
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            return

    async def send_json(self, payload: dict):
        await self.send(text_data=json.dumps(payload))
