"""
Serializers for Detection app.
"""
from rest_framework import serializers
from .models import DetectionRecord, ViolationRecord, DetectionSession


class DetectionRecordSerializer(serializers.ModelSerializer):
    """Serializer for DetectionRecord model."""
    class Meta:
        model = DetectionRecord
        fields = ['id', 'frame_id', 'timestamp', 'detected_count',
                  'compliant_count', 'non_compliant_count',
                  'detections', 'image_path', 'session_id']
        read_only_fields = ['id', 'timestamp']


class ViolationRecordSerializer(serializers.ModelSerializer):
    """Serializer for ViolationRecord model."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ViolationRecord
        fields = ['id', 'violation_id', 'timestamp', 'worker_id',
                  'worker_name', 'missing_ppe', 'detected_ppe',
                  'image', 'image_url', 'bounding_box',
                  'severity', 'status', 'notes',
                  'alert_sent', 'alert_sent_at',
                  'resolved_at', 'resolved_by']
        read_only_fields = ['id', 'timestamp', 'image_url']

    def get_image_url(self, obj):
        """Get full image URL."""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ViolationRecordUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating violation records."""
    class Meta:
        model = ViolationRecord
        fields = ['status', 'severity', 'notes', 'resolved_at']


class DetectionSessionSerializer(serializers.ModelSerializer):
    """Serializer for DetectionSession model."""
    class Meta:
        model = DetectionSession
        fields = ['id', 'session_id', 'start_time', 'end_time',
                  'status', 'total_frames', 'total_detections',
                  'total_violations', 'location', 'camera_id', 'started_by']
        read_only_fields = ['id', 'start_time']


class ImageUploadSerializer(serializers.Serializer):
    """Serializer for image upload requests."""
    image = serializers.ImageField(
        help_text="Image file for PPE detection (JPG, PNG, WebP)"
    )
    session_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional session ID for grouping detections"
    )
    required_ppe = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of required PPE types for this detection"
    )
    confidence_threshold = serializers.FloatField(
        required=False,
        min_value=0.0,
        max_value=1.0,
        help_text="Confidence threshold for detections (0.0 - 1.0)"
    )
