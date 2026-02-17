"""
Views for Workers app.
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Worker, WorkerShift
from .serializers import (
    WorkerSerializer,
    WorkerCreateSerializer,
    WorkerUpdateSerializer,
    WorkerDetailSerializer,
    WorkerShiftSerializer
)


class WorkerListCreateView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating workers.

    GET /api/workers/ - List all workers
    POST /api/workers/ - Create a new worker
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Worker.objects.all()

        # Filter by department
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(department=department)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Search by name or worker_id
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                name__icontains=search
            ) | queryset.filter(
                worker_id__icontains=search
            )

        return queryset.order_by('name')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WorkerCreateSerializer
        return WorkerSerializer

    def perform_create(self, serializer):
        # Set the created_by field to the current user
        serializer.save(created_by=self.request.user)


class WorkerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for worker details.

    GET /api/workers/{id}/ - Get worker details
    PUT /api/workers/{id}/ - Update worker
    PATCH /api/workers/{id}/ - Partially update worker
    DELETE /api/workers/{id}/ - Delete worker
    """
    queryset = Worker.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return WorkerDetailSerializer
        elif self.request.method in ['PUT', 'PATCH']:
            return WorkerUpdateSerializer
        return WorkerSerializer


class WorkerByWorkerIdView(generics.RetrieveAPIView):
    """
    API endpoint for getting worker by worker_id.

    GET /api/workers/id/{worker_id}/ - Get worker by worker_id
    """
    queryset = Worker.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = WorkerDetailSerializer
    lookup_field = 'worker_id'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_stats(request):
    """
    Get worker statistics.

    GET /api/workers/stats/ - Get overall worker statistics
    """
    from django.db.models import Count, Q

    total_workers = Worker.objects.count()
    active_workers = Worker.objects.filter(is_active=True).count()

    # Workers by department
    dept_stats = Worker.objects.values('department').annotate(
        count=Count('id')
    ).order_by('-count')

    # Workers with violations
    from detection.models import ViolationRecord
    workers_with_violations = ViolationRecord.objects.values('worker_id').distinct().count()

    return Response({
        'total_workers': total_workers,
        'active_workers': active_workers,
        'inactive_workers': total_workers - active_workers,
        'workers_with_violations': workers_with_violations,
        'by_department': list(dept_stats)
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def worker_shifts(request, worker_id):
    """
    Get or create shifts for a worker.

    GET /api/workers/{worker_id}/shifts/ - Get worker's shifts
    POST /api/workers/{worker_id}/shifts/ - Create a new shift
    """
    worker = get_object_or_404(Worker, worker_id=worker_id)

    if request.method == 'GET':
        shifts = worker.shifts.all()
        serializer = WorkerShiftSerializer(shifts, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = WorkerShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(worker=worker)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_violations(request, worker_id):
    """
    Get violations for a specific worker.

    GET /api/workers/{worker_id}/violations/ - Get worker's violation history
    """
    worker = get_object_or_404(Worker, worker_id=worker_id)

    from detection.models import ViolationRecord
    violations = ViolationRecord.objects.filter(
        worker_id=worker_id
    ).order_by('-timestamp')

    # Apply status filter
    violation_status = request.query_params.get('status')
    if violation_status:
        violations = violations.filter(status=violation_status)

    # Paginate
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size

    violations_page = violations[start:end]

    from detection.serializers import ViolationRecordSerializer
    return Response({
        'worker_id': worker_id,
        'worker_name': worker.name,
        'total_violations': violations.count(),
        'page': page,
        'page_size': page_size,
        'violations': ViolationRecordSerializer(
            violations_page,
            many=True,
            context={'request': request}
        ).data
    })
