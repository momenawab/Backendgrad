"""
Serializers for the Content app.
"""
from rest_framework import serializers
from .models import HowToStep


class HowToStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = HowToStep
        fields = ['id', 'order', 'title', 'description', 'image_url']
