"""
Admin configuration for Detection app.
"""
from django.contrib import admin
from .models import DetectionRecord, ViolationRecord, DetectionSession


@admin.register(DetectionRecord)
class DetectionRecordAdmin(admin.ModelAdmin):
    """Admin interface for DetectionRecord model."""
    list_display = ['frame_id', 'timestamp', 'detected_count',
                    'compliant_count', 'non_compliant_count', 'session_id']
    list_filter = ['timestamp', 'session_id']
    search_fields = ['frame_id', 'session_id']
    ordering = ['-timestamp']
    readonly_fields = ['frame_id', 'timestamp', 'detections']


@admin.register(ViolationRecord)
class ViolationRecordAdmin(admin.ModelAdmin):
    """Admin interface for ViolationRecord model."""
    list_display = ['violation_id', 'timestamp', 'worker_id', 'worker_name',
                    'severity', 'status', 'alert_sent']
    list_filter = ['severity', 'status', 'alert_sent', 'timestamp']
    search_fields = ['violation_id', 'worker_id', 'worker_name']
    ordering = ['-timestamp']
    readonly_fields = ['violation_id', 'timestamp', 'alert_sent_at']

    fieldsets = (
        ('Violation Info', {
            'fields': ('violation_id', 'worker_id', 'worker_name', 'image')
        }),
        ('Detection Data', {
            'fields': ('missing_ppe', 'detected_ppe', 'bounding_box')
        }),
        ('Status', {
            'fields': ('severity', 'status', 'notes')
        }),
        ('Alert Info', {
            'fields': ('alert_sent', 'alert_sent_at')
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolved_by')
        }),
    )


@admin.register(DetectionSession)
class DetectionSessionAdmin(admin.ModelAdmin):
    """Admin interface for DetectionSession model."""
    list_display = ['session_id', 'start_time', 'end_time', 'status',
                    'total_frames', 'total_detections', 'total_violations']
    list_filter = ['status', 'start_time', 'location']
    search_fields = ['session_id', 'location', 'camera_id']
    ordering = ['-start_time']
    readonly_fields = ['session_id', 'start_time']
