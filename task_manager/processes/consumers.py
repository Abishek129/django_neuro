import asyncio
import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer

from . import services


class UnifiedProcessesConsumer(AsyncWebsocketConsumer):
    channel_layer_alias = "task_manager"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming_task = None
        self.error_task = None
        self.interval = 2
        self.limit = 50
        self.latest_pids = []

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)

        # Parse interval (1-60 seconds)
        interval_param = params.get("interval", [None])[0]
        if interval_param:
            try:
                self.interval = max(1, min(60, float(interval_param)))
            except (ValueError, TypeError):
                pass

        # Parse limit (1-200 processes)
        limit_param = params.get("limit", ["50"])[0]
        try:
            self.limit = max(1, min(200, int(limit_param)))
        except (ValueError, TypeError):
            self.limit = 50

        await self.accept()
        self.streaming_task = asyncio.create_task(self._stream_loop())
        self.error_task = asyncio.create_task(self._error_collection_loop())

    async def disconnect(self, close_code):
        for task in (self.streaming_task, self.error_task):
            if task:
                task.cancel()
                try:
                    await task
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

        elif message.get("type") == "set_limit":
            new_limit = message.get("limit")
            if new_limit is not None:
                try:
                    self.limit = max(1, min(200, int(new_limit)))
                except (ValueError, TypeError):
                    pass

        elif message.get("type") == "get_errors":
            pid = message.get("pid")
            if pid is not None:
                try:
                    data = await asyncio.to_thread(
                        services.get_process_errors, int(pid)
                    )
                    await self.send(text_data=json.dumps({
                        "type": "process_errors",
                        "data": data,
                    }))
                except (ValueError, TypeError):
                    pass

    async def _stream_loop(self):
        try:
            while True:
                data = await asyncio.to_thread(
                    services.get_unified_processes,
                    limit=self.limit
                )

                # Attach cached error summaries to each process
                pids = [p['pid'] for p in data['processes']]
                self.latest_pids = pids
                error_summaries = await asyncio.to_thread(
                    services.get_cached_error_summaries, pids
                )
                for proc in data['processes']:
                    summary = error_summaries.get(proc['pid'], {})
                    proc['error_count'] = summary.get('error_count', 0)
                    proc['health'] = summary.get('health', 'healthy')
                    proc['last_error'] = summary.get('last_error', None)

                await self.send(text_data=json.dumps({
                    "type": "unified_processes",
                    "data": data,
                }))
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            return

    async def _error_collection_loop(self):
        """Background loop: refresh error cache from journald every 30 seconds."""
        try:
            while True:
                pids = self.latest_pids[:20]
                if pids:
                    await asyncio.to_thread(services.refresh_error_cache, pids)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            return
