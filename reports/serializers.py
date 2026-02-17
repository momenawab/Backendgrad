"""
Serializers for Reports app.
"""
from rest_framework import serializers
from .models import ReportSchedule, GeneratedReport


class ReportScheduleSerializer(serializers.ModelSerializer):
    """Serializer for ReportSchedule model."""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ReportSchedule
        fields = ['id', 'name', 'description', 'report_type', 'frequency',
                  'recipients', 'filters', 'is_active', 'last_sent', 'next_send',
                  'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['id', 'last_sent', 'next_send', 'created_at']

    def get_created_by_name(self, obj):
        """Get creator name."""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for GeneratedReport model."""
    generated_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = ['id', 'report_id', 'title', 'report_type', 'format',
                  'file_path', 'file_size', 'parameters', 'status',
                  'error_message', 'created_at', 'completed_at', 'expires_at',
                  'generated_by', 'generated_by_name', 'download_url']
        read_only_fields = ['id', 'report_id', 'created_at', 'completed_at']

    def get_generated_by_name(self, obj):
        """Get generator name."""
        if obj.generated_by:
            return obj.generated_by.get_full_name() or obj.generated_by.username
        return None

    def get_download_url(self, obj):
        """Get download URL."""
        if obj.file_path and obj.status == 'completed':
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/api/reports/download/{obj.report_id}/')
        return None


class ReportRequestSerializer(serializers.Serializer):
    """Serializer for report generation requests."""
    report_type = serializers.ChoiceField(choices=[
        'summary', 'violations', 'compliance', 'worker'
    ])
    format = serializers.ChoiceField(choices=['csv', 'json'], default='json')
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    department = serializers.CharField(required=False, allow_blank=True)
    worker_id = serializers.CharField(required=False, allow_blank=True)
