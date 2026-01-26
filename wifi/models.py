from django.db import models


class SavedNetwork(models.Model):
    """
    Represents a saved/known WiFi network profile.
    Similar to how NetworkManager stores connection profiles in /etc/NetworkManager/system-connections/
    """

    SECURITY_CHOICES = [
        ("open", "Open"),
        ("wep", "WEP"),
        ("wpa", "WPA"),
        ("wpa2", "WPA2"),
        ("wpa3", "WPA3"),
        ("wpa2_enterprise", "WPA2 Enterprise"),
        ("wpa3_enterprise", "WPA3 Enterprise"),
    ]

    ssid = models.CharField(max_length=32, unique=True, help_text="Network name (max 32 chars per WiFi spec)")
    security_type = models.CharField(max_length=20, choices=SECURITY_CHOICES, default="wpa2")
    password = models.CharField(max_length=63, blank=True, help_text="PSK password (8-63 chars for WPA)")

    # Connection settings
    auto_connect = models.BooleanField(default=True, help_text="Automatically connect when in range")
    priority = models.IntegerField(default=0, help_text="Higher priority networks connect first")
    hidden = models.BooleanField(default=False, help_text="Network does not broadcast SSID")

    # Optional BSSID lock (connect only to specific access point)
    bssid = models.CharField(max_length=17, blank=True, help_text="MAC address of specific AP (XX:XX:XX:XX:XX:XX)")

    # Metered connection (limit background data)
    metered = models.BooleanField(default=False, help_text="Treat as metered connection")

    # Timestamps
    last_connected = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-last_connected"]
        verbose_name = "Saved Network"
        verbose_name_plural = "Saved Networks"

    def __str__(self):
        return f"{self.ssid} ({self.security_type})"

    @property
    def is_open(self):
        return self.security_type == "open"


class ConnectionLog(models.Model):
    """
    Log of WiFi connection events for history/debugging.
    """

    EVENT_CHOICES = [
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("failed", "Connection Failed"),
        ("auth_failed", "Authentication Failed"),
    ]

    network = models.ForeignKey(SavedNetwork, on_delete=models.CASCADE, related_name="connection_logs")
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Connection details at time of event
    signal_strength = models.IntegerField(null=True, blank=True, help_text="Signal strength 0-100")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    bssid = models.CharField(max_length=17, blank=True, help_text="AP MAC address connected to")

    # Error info for failed connections
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Connection Log"
        verbose_name_plural = "Connection Logs"

    def __str__(self):
        return f"{self.network.ssid} - {self.event} at {self.timestamp}"
