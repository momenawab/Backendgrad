"""
WebSocket routing configuration for Detection app.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/detect/$', consumers.DetectionConsumer.as_asgi()),
]
