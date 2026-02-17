"""
Admin configuration for Workers app.
"""
from django.contrib import admin
from .models import Worker, WorkerShift


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    """Admin interface for Worker model."""
    list_display = ['worker_id', 'name', 'department', 'position',
                    'shift', 'is_active', 'compliance_rate']
    list_filter = ['department', 'shift', 'is_active', 'created_at']
    search_fields = ['worker_id', 'name', 'email', 'employee_id']
    ordering = ['name']
    readonly_fields = ['compliance_rate', 'created_at', 'updated_at']

    fieldsets = (
        ('Worker Information', {
            'fields': ('worker_id', 'name', 'email', 'phone', 'photo')
        }),
        ('Employment Details', {
            'fields': ('department', 'position', 'shift', 'hire_date',
                      'employee_id', 'supervisor')
        }),
        ('PPE Requirements', {
            'fields': ('required_ppe',)
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_by', 'compliance_rate', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WorkerShift)
class WorkerShiftAdmin(admin.ModelAdmin):
    """Admin interface for WorkerShift model."""
    list_display = ['worker', 'date', 'shift_type', 'check_in', 'check_out',
                    'violations_count', 'alerts_triggered']
    list_filter = ['shift_type', 'date']
    search_fields = ['worker__name', 'worker__worker_id']
    ordering = ['-date', 'shift_type']
    readonly_fields = ['created_at']
