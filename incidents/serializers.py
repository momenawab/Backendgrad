from rest_framework import serializers
from .models import Incident


class IncidentSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    reported_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            'id', 'title', 'description', 'severity', 'location', 'status',
            'photo', 'photo_url', 'reported_by', 'reported_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'reported_by', 'created_at', 'updated_at']

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return None

    def get_reported_by_name(self, obj):
        return obj.reported_by.username if obj.reported_by else None
