"""
Models for the Incidents app (F15) — manual incident / near-miss reports that
the camera pipeline can't capture (spills, near-misses, equipment faults).
"""
from django.conf import settings
from django.db import models


def incident_photo_path(instance, filename):
    return f'incidents/{filename}'


class Incident(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    location = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    photo = models.ImageField(upload_to=incident_photo_path, blank=True, null=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_incidents',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'incidents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.severity})"
