"""
Serializers for the Cameras app.
"""
from rest_framework import serializers
from .models import Camera


class CameraSerializer(serializers.ModelSerializer):
    """Serializer for the Camera model."""

    class Meta:
        model = Camera
        fields = [
            'id', 'name', 'ip_address', 'location', 'status',
            'thumbnail_url', 'last_seen', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_seen', 'created_at', 'updated_at']
