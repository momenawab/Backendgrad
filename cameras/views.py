"""
Views for the Cameras app.

CRUD over the camera inventory plus a lightweight health-ping endpoint that
updates a camera's status/last_seen (e.g. polled by the dashboard).
"""
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Camera
from .serializers import CameraSerializer


class CameraListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/cameras/   -> list cameras
    POST /api/cameras/   -> add a camera
    """
    serializer_class = CameraSerializer
    permission_classes = [IsAuthenticated]
    queryset = Camera.objects.all()


class CameraDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/cameras/{id}/
    """
    serializer_class = CameraSerializer
    permission_classes = [IsAuthenticated]
    queryset = Camera.objects.all()
    lookup_field = 'id'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def camera_health(request, id):
    """
    POST /api/cameras/{id}/health/

    Body (optional): { "status": "online|offline|error" }
    Updates the camera's status and last_seen timestamp.
    """
    try:
        camera = Camera.objects.get(id=id)
    except Camera.DoesNotExist:
        return Response({'error': 'Camera not found'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status', 'online')
    valid = dict(Camera.STATUS_CHOICES)
    if new_status not in valid:
        return Response(
            {'error': f"Invalid status. Choose from {list(valid)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    camera.status = new_status
    camera.last_seen = timezone.now()
    camera.save(update_fields=['status', 'last_seen', 'updated_at'])

    return Response(CameraSerializer(camera).data, status=status.HTTP_200_OK)
