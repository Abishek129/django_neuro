from django.db import models


class Device(models.Model):
    device_id = models.CharField(max_length=128, unique=True)
    physical_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=64)
    connection = models.CharField(max_length=64)
    mac_address = models.CharField(max_length=64, blank=True, null=True)
    is_connected = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.device_id})"
