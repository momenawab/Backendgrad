"""
Detection models for SafeSight PPE Detection System.
"""
from django.db import models
from django.conf import settings
import os
import json


def violation_image_upload_path(instance, filename):
    """Generate upload path for violation images."""
    ext = os.path.splitext(filename)[1]
    timestamp = instance.timestamp.strftime('%Y%m%d_%H%M%S')
    return f'violations/{instance.worker_id or "unknown"}_{timestamp}{ext}'


class DetectionRecord(models.Model):
    """
    Stores historical detection results from PPE analysis.
    """
    frame_id = models.CharField(max_length=100, unique=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Detection summary counts
    detected_count = models.IntegerField(default=0)
    compliant_count = models.IntegerField(default=0)
    non_compliant_count = models.IntegerField(default=0)

    # Full detection results as JSON
    detections = models.JSONField(default=list)

    # Image reference (optional)
    image_path = models.CharField(max_length=500, blank=True, null=True)

    # Session info
    session_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'detection_records'
        verbose_name_plural = "Detection Records"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['session_id']),
        ]

    def __str__(self):
        return f"Detection {self.frame_id} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class ViolationRecord(models.Model):
    """
    Records PPE violations with images for review and reporting.
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    violation_id = models.CharField(max_length=100, unique=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Worker info
    worker_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    worker_name = models.CharField(max_length=200, blank=True, null=True)

    # Detection data
    missing_ppe = models.JSONField(default=list, help_text="List of missing PPE types")
    detected_ppe = models.JSONField(default=list, help_text="List of detected PPE types")

    # Image and bounding box
    image = models.ImageField(upload_to=violation_image_upload_path)
    bounding_box = models.JSONField(help_text="Bounding box coordinates")

    # Status and severity
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # Notes
    notes = models.TextField(blank=True, null=True)

    # Alert reference
    alert_sent = models.BooleanField(default=False)
    alert_sent_at = models.DateTimeField(blank=True, null=True)

    # Resolution
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_violations'
    )

    class Meta:
        db_table = 'violation_records'
        verbose_name_plural = "Violation Records"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['worker_id']),
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        worker = self.worker_name or self.worker_id or "Unknown"
        return f"Violation {self.violation_id} - {worker} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class DetectionSession(models.Model):
    """
    Tracks detection sessions for monitoring and analytics.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]

    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Session stats
    total_frames = models.IntegerField(default=0)
    total_detections = models.IntegerField(default=0)
    total_violations = models.IntegerField(default=0)

    # Session metadata
    location = models.CharField(max_length=200, blank=True, null=True)
    camera_id = models.CharField(max_length=100, blank=True, null=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detection_sessions'
    )

    class Meta:
        db_table = 'detection_sessions'
        verbose_name_plural = "Detection Sessions"
        ordering = ['-start_time']

    def __str__(self):
        return f"Session {self.session_id} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
