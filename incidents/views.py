from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated

from .models import Incident
from .serializers import IncidentSerializer


class IncidentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/incidents/"""
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Incident.objects.all()

    def get_queryset(self):
        qs = Incident.objects.all()
        status_f = self.request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        return qs

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)


class IncidentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/incidents/{id}/"""
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Incident.objects.all()
    lookup_field = 'id'
