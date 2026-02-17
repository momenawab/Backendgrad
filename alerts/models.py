"""
Alert system models for SafeSight PPE Detection System.
"""
from django.db import models
from django.conf import settings


class AlertConfig(models.Model):
    """
    Alert configuration settings for the system.
    """
    ALERT_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('webhook', 'Webhook'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Configuration identifier
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    # Alert type and destination
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    destination = models.CharField(
        max_length=500,
        help_text="Email address, phone number, webhook URL, etc."
    )

    # Severity threshold - only send alerts for violations at or above this level
    min_severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium'
    )

    # Violation count threshold - send alert after N violations
    violation_threshold = models.IntegerField(
        default=1,
        help_text="Number of violations before triggering alert"
    )

    # Time window for threshold (minutes)
    time_window_minutes = models.IntegerField(
        default=60,
        help_text="Time window in which to count violations"
    )

    # Enabled status
    is_active = models.BooleanField(default=True)

    # Department filter (null = all departments)
    department_filter = models.CharField(max_length=50, blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_alert_configs'
    )

    class Meta:
        db_table = 'alert_configs'
        verbose_name_plural = "Alert Configurations"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.alert_type})"


class AlertHistory(models.Model):
    """
    Historical record of alerts sent by the system.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]

    alert_id = models.CharField(max_length=100, unique=True, db_index=True)

    # Reference to config
    config = models.ForeignKey(
        AlertConfig,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts'
    )

    # Alert details
    alert_type = models.CharField(max_length=20)
    destination = models.CharField(max_length=500)
    subject = models.CharField(max_length=200)
    message = models.TextField()

    # Violation reference
    violation = models.ForeignKey(
        'detection.ViolationRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts'
    )

    # Severity
    severity = models.CharField(max_length=20)

    # Delivery status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)

    # Retry count
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    # Metadata
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_alerts'
    )

    class Meta:
        db_table = 'alert_history'
        verbose_name_plural = "Alert History"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        return f"Alert {self.alert_id} - {self.subject}"


class AlertRecipient(models.Model):
    """
    Individual alert recipients for notifications.
    """
    ROLE_CHOICES = [
        ('supervisor', 'Supervisor'),
        ('manager', 'Manager'),
        ('safety_officer', 'Safety Officer'),
        ('admin', 'Administrator'),
    ]

    recipient_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    # Contact information
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Notification preferences
    receive_email_alerts = models.BooleanField(default=True)
    receive_sms_alerts = models.BooleanField(default=False)
    receive_push_alerts = models.BooleanField(default=False)

    # Severity threshold for this recipient
    min_severity = models.CharField(
        max_length=20,
        choices=AlertConfig.SEVERITY_CHOICES,
        default='high'
    )

    # Department filter (null = all departments)
    department_filter = models.CharField(max_length=50, blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alert_recipients'
        verbose_name_plural = "Alert Recipients"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"
