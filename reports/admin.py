"""
Admin configuration for Reports app.
"""
from django.contrib import admin
from .models import ReportSchedule, GeneratedReport


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    """Admin interface for ReportSchedule model."""
    list_display = ['name', 'report_type', 'frequency', 'is_active', 'last_sent', 'next_send']
    list_filter = ['report_type', 'frequency', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['last_sent', 'created_at']


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    """Admin interface for GeneratedReport model."""
    list_display = ['title', 'report_type', 'format', 'status', 'created_at', 'generated_by']
    list_filter = ['report_type', 'format', 'status', 'created_at']
    search_fields = ['title', 'report_id']
    ordering = ['-created_at']
    readonly_fields = ['report_id', 'created_at', 'completed_at', 'file_size']
