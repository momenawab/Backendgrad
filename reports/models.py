"""
Reports module for SafeSight PPE Detection System.

Note: This app primarily uses data from detection models (DetectionRecord, ViolationRecord)
rather than defining its own models. Report generation happens on-demand via views.
"""
from django.db import models


class ReportSchedule(models.Model):
    """
    Scheduled reports for automatic generation.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    REPORT_TYPE_CHOICES = [
        ('summary', 'Summary Report'),
        ('violations', 'Violation Report'),
        ('compliance', 'Compliance Report'),
        ('worker', 'Worker Report'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)

    # Recipients (comma-separated emails)
    recipients = models.TextField(help_text="Comma-separated email addresses")

    # Filters for the report (JSON)
    filters = models.JSONField(default=dict, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(blank=True, null=True)
    next_send = models.DateTimeField(blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_reports'
    )

    class Meta:
        db_table = 'report_schedules'
        verbose_name_plural = "Report Schedules"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"


class GeneratedReport(models.Model):
    """
    Track generated reports for download access.
    """
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]

    report_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)

    # File reference
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)

    # Report parameters
    parameters = models.JSONField(default=dict, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    # Metadata
    generated_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )

    class Meta:
        db_table = 'generated_reports'
        verbose_name_plural = "Generated Reports"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['report_type']),
        ]

    def __str__(self):
        return f"{self.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
