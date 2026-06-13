from django.contrib import admin
from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['title', 'severity', 'status', 'location', 'reported_by', 'created_at']
    list_filter = ['severity', 'status', 'created_at']
    search_fields = ['title', 'description', 'location']
