from django.db import models


class Event(models.Model):
    METRIC_CHOICES = [
        ("cpu", "CPU"),
        ("ram", "RAM"),
        ("swap", "Swap"),
        ("disk", "Disk"),
        ("gpu_util", "GPU Utilization"),
        ("gpu_mem", "GPU Memory"),
        ("bmc_temp", "BMC Temperature"),
        ("bmc_fan", "BMC Fan"),
        ("bmc_power", "BMC Power"),
    ]
    SEVERITY_CHOICES = [
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    message = models.TextField()
    value = models.FloatField()
    threshold = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.metric}: {self.value}% (threshold {self.threshold}%)"
