from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    """
    GET /api/audit/  — admin-only. Filters: ?user=, ?action=, ?start_date=, ?end_date=
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) not in ('admin', 'supervisor'):
            raise PermissionDenied('Audit log is restricted to admins.')
        qs = AuditLog.objects.all()
        p = self.request.query_params
        if p.get('user'):
            qs = qs.filter(user_id=p['user'])
        if p.get('action'):
            qs = qs.filter(action__icontains=p['action'])
        if p.get('start_date'):
            qs = qs.filter(created_at__gte=p['start_date'])
        if p.get('end_date'):
            qs = qs.filter(created_at__lte=p['end_date'])
        return qs
