"""
Admin configuration for Alerts app.
"""
from django.contrib import admin
from .models import AlertConfig, AlertHistory, AlertRecipient


@admin.register(AlertConfig)
class AlertConfigAdmin(admin.ModelAdmin):
    """Admin interface for AlertConfig model."""
    list_display = ['name', 'alert_type', 'min_severity', 'violation_threshold',
                    'is_active', 'department_filter']
    list_filter = ['alert_type', 'min_severity', 'is_active', 'department_filter']
    search_fields = ['name', 'description', 'destination']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Configuration', {
            'fields': ('name', 'description', 'alert_type', 'destination')
        }),
        ('Thresholds', {
            'fields': ('min_severity', 'violation_threshold', 'time_window_minutes')
        }),
        ('Filters', {
            'fields': ('is_active', 'department_filter')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AlertHistory)
class AlertHistoryAdmin(admin.ModelAdmin):
    """Admin interface for AlertHistory model."""
    list_display = ['alert_id', 'alert_type', 'destination', 'severity',
                    'status', 'created_at', 'sent_at']
    list_filter = ['alert_type', 'severity', 'status', 'created_at']
    search_fields = ['alert_id', 'subject', 'destination']
    ordering = ['-created_at']
    readonly_fields = ['alert_id', 'created_at', 'sent_at']

    fieldsets = (
        ('Alert Details', {
            'fields': ('alert_id', 'config', 'alert_type', 'destination')
        }),
        ('Content', {
            'fields': ('subject', 'message')
        }),
        ('Status', {
            'fields': ('status', 'severity', 'error_message', 'retry_count')
        }),
        ('Related', {
            'fields': ('violation', 'triggered_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at')
        }),
    )


@admin.register(AlertRecipient)
class AlertRecipientAdmin(admin.ModelAdmin):
    """Admin interface for AlertRecipient model."""
    list_display = ['name', 'role', 'email', 'phone', 'min_severity', 'is_active']
    list_filter = ['role', 'is_active', 'department_filter']
    search_fields = ['name', 'recipient_id', 'email', 'phone']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Recipient Information', {
            'fields': ('recipient_id', 'name', 'role', 'email', 'phone')
        }),
        ('Notification Preferences', {
            'fields': ('receive_email_alerts', 'receive_sms_alerts', 'receive_push_alerts')
        }),
        ('Settings', {
            'fields': ('min_severity', 'department_filter', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
