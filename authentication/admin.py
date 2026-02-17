"""
Admin configuration for Authentication app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, WorkerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""
    list_display = ['username', 'email', 'role', 'department', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-created_at']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'department')}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'department', 'email')}),
    )


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    """Admin interface for WorkerProfile model."""
    list_display = ['worker_id', 'name', 'department', 'position', 'is_active', 'created_at']
    list_filter = ['department', 'is_active', 'created_at']
    search_fields = ['worker_id', 'name', 'department']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Worker Information', {
            'fields': ('worker_id', 'name', 'department', 'position', 'photo')
        }),
        ('PPE Requirements', {
            'fields': ('required_ppe',)
        }),
        ('Status', {
            'fields': ('is_active', 'hire_date', 'user')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
