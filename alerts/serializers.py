"""
Serializers for Alerts app.
"""
from rest_framework import serializers
from .models import AlertConfig, AlertHistory, AlertRecipient


class AlertConfigSerializer(serializers.ModelSerializer):
    """Serializer for AlertConfig model."""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AlertConfig
        fields = ['id', 'name', 'description', 'alert_type', 'destination',
                  'min_severity', 'violation_threshold', 'time_window_minutes',
                  'is_active', 'department_filter', 'created_by', 'created_by_name',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        """Get creator name."""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class AlertConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating alert configurations."""
    class Meta:
        model = AlertConfig
        fields = ['name', 'description', 'alert_type', 'destination',
                  'min_severity', 'violation_threshold', 'time_window_minutes',
                  'is_active', 'department_filter']


class AlertHistorySerializer(serializers.ModelSerializer):
    """Serializer for AlertHistory model."""
    violation_details = serializers.SerializerMethodField()
    config_name = serializers.SerializerMethodField()

    class Meta:
        model = AlertHistory
        fields = ['id', 'alert_id', 'config', 'config_name', 'alert_type',
                  'destination', 'subject', 'message', 'violation', 'violation_details',
                  'severity', 'status', 'error_message', 'retry_count',
                  'created_at', 'sent_at', 'triggered_by']
        read_only_fields = ['id', 'alert_id', 'created_at']

    def get_violation_details(self, obj):
        """Get violation details if available."""
        if obj.violation:
            return {
                'violation_id': obj.violation.violation_id,
                'worker_id': obj.violation.worker_id,
                'worker_name': obj.violation.worker_name,
                'missing_ppe': obj.violation.missing_ppe,
            }
        return None

    def get_config_name(self, obj):
        """Get config name."""
        if obj.config:
            return obj.config.name
        return None


class AlertRecipientSerializer(serializers.ModelSerializer):
    """Serializer for AlertRecipient model."""
    class Meta:
        model = AlertRecipient
        fields = ['id', 'recipient_id', 'name', 'role', 'email', 'phone',
                  'receive_email_alerts', 'receive_sms_alerts', 'receive_push_alerts',
                  'min_severity', 'department_filter', 'is_active',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AlertRecipientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating alert recipients."""
    class Meta:
        model = AlertRecipient
        fields = ['recipient_id', 'name', 'role', 'email', 'phone',
                  'receive_email_alerts', 'receive_sms_alerts', 'receive_push_alerts',
                  'min_severity', 'department_filter', 'is_active']


class TestAlertSerializer(serializers.Serializer):
    """Serializer for testing alert system."""
    alert_type = serializers.ChoiceField(choices=['email', 'sms', 'push', 'webhook'])
    destination = serializers.CharField(max_length=500)
    message = serializers.CharField(required=False, default='This is a test alert from SafeSight.')
