from django.core.management.base import BaseCommand

from task_manager.cpu.agent import run


class Command(BaseCommand):
    help = "Run the CPU usage agent that records usage to Redis every minute"

    def handle(self, *args, **options):
        self.stdout.write("Starting CPU usage agent...")
        run()
