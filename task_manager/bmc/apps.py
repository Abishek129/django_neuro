import asyncio
import threading
from django.apps import AppConfig


class BmcConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'task_manager.bmc'

    def ready(self):
        """Start background logging when Django is ready."""
        from .services.hwmon_service import start_background_logging

        # Start the background task in a separate thread
        def run_background():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.create_task(start_background_logging())
            loop.run_forever()

        thread = threading.Thread(target=run_background, daemon=True)
        thread.start()
