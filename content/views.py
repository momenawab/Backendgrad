"""
Views for the Content app.
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import HowToStep
from .serializers import HowToStepSerializer


class HowToStepListView(generics.ListAPIView):
    """
    GET /api/content/how-to/  -> ordered list of active how-to steps.
    """
    serializer_class = HowToStepSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return HowToStep.objects.filter(is_active=True)
