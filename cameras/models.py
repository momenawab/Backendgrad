"""
Models for the Cameras app.

Cameras are persisted metadata entities used by the dashboard / camera
management pages on both the React website and the Flutter app. Live frame
analysis itself is handled by the existing `/ws/detect/` WebSocket consumer;
this model only stores the camera inventory and its last-known status.
"""
from django.db import models


class Camera(models.Model):
    """A monitored camera / video source."""

    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ]

    name = models.CharField(max_length=200)
    ip_address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="IP address or stream URL of the camera"
    )
    location = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='offline',
        db_index=True,
    )
    thumbnail_url = models.URLField(blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cameras'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.status})"
