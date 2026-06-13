"""
URL configuration for the Cameras app.
"""
from django.urls import path
from .views import CameraListCreateView, CameraDetailView, camera_health

urlpatterns = [
    path('', CameraListCreateView.as_view(), name='camera-list'),
    path('<int:id>/', CameraDetailView.as_view(), name='camera-detail'),
    path('<int:id>/health/', camera_health, name='camera-health'),
]
