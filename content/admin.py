"""
Admin configuration for the Content app.
"""
from django.contrib import admin
from .models import HowToStep


@admin.register(HowToStep)
class HowToStepAdmin(admin.ModelAdmin):
    list_display = ['order', 'title', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['title', 'description']
    ordering = ['order']
