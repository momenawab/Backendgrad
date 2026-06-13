"""
Admin configuration for the Cameras app.
"""
from django.contrib import admin
from .models import Camera


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'location', 'status', 'last_seen', 'is_active']
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['name', 'ip_address', 'location']
    ordering = ['name']
