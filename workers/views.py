"""
Views for Workers app.
"""
import logging
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Worker, WorkerShift
from .serializers import (
    WorkerSerializer,
    WorkerCreateSerializer,
    WorkerUpdateSerializer,
    WorkerDetailSerializer,
    WorkerShiftSerializer
)

logger = logging.getLogger(__name__)


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

    def perform_destroy(self, instance):
        # F16 audit: record worker deletion.
        from audit.services import record_audit
        record_audit(self.request.user, 'worker_delete',
                     target_type='Worker', target_id=instance.worker_id,
                     name=instance.name)
        instance.delete()


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_violations_summary(request):
    """
    Per-worker violation totals for the reports screen.

    GET /api/workers/violations-summary/
    Returns a list of {worker_id, name, photo_url, violation_count, total_detections}.
    """
    from django.db.models import Count
    from detection.models import ViolationRecord

    counts = dict(
        ViolationRecord.objects
        .exclude(worker_id__isnull=True)
        .exclude(worker_id='')
        .values_list('worker_id')
        .annotate(c=Count('id'))
    )

    results = []
    for worker in Worker.objects.all().order_by('name'):
        violation_count = counts.get(worker.worker_id, 0)
        photo_url = None
        if worker.photo:
            try:
                photo_url = request.build_absolute_uri(worker.photo.url)
            except Exception:
                photo_url = None
        results.append({
            'worker_id': worker.worker_id,
            'name': worker.name,
            'photo_url': photo_url,
            'violation_count': violation_count,
            # No per-worker detection tally exists yet; mirror violation_count
            # so the client renders without divide-by-zero. Replace once
            # DetectionRecord tracks worker_id.
            'total_detections': violation_count,
        })

    return Response(results)


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_worker_with_photo(request):
    """
    Add a new worker with face photo for recognition.

    POST /api/workers/add-with-photo/

    Body (multipart/form-data):
        worker_id: string (required)
        name: string (required)
        photo: file (required - clear face photo)
        email: string (optional)
        phone: string (optional)
        department: string (optional)
        position: string (optional)
        shift: string (optional)
        required_ppe: array (optional)
    """
    from detection.services.face_recognition import FaceRecognitionService
    import numpy as np

    try:
        # Extract data
        worker_id = request.data.get('worker_id')
        name = request.data.get('name')
        photo = request.data.get('photo')

        if not all([worker_id, name, photo]):
            return Response({
                'error': 'worker_id, name, and photo are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if worker_id already exists
        if Worker.objects.filter(worker_id=worker_id).exists():
            return Response({
                'error': 'A worker with this ID already exists'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Extract face encoding from photo
        face_encoding = FaceRecognitionService.extract_face_encoding(photo.read())

        if face_encoding is None:
            return Response({
                'error': 'No face detected in the uploaded photo. Please upload a clear photo showing the face.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Normalize required_ppe — multipart form data sends it as a CSV string
        # (e.g. "safetyGlasses,vest,gloves") but the JSONField expects a list.
        raw_ppe = request.data.get('required_ppe', [])
        if isinstance(raw_ppe, str):
            required_ppe_list = [p.strip() for p in raw_ppe.split(',') if p.strip()]
        elif isinstance(raw_ppe, (list, tuple)):
            required_ppe_list = list(raw_ppe)
        else:
            required_ppe_list = []

        # Create worker with face encoding
        worker = Worker.objects.create(
            worker_id=worker_id,
            name=name,
            email=request.data.get('email'),
            phone=request.data.get('phone'),
            department=request.data.get('department'),
            position=request.data.get('position'),
            shift=request.data.get('shift', 'day'),
            photo=photo,
            required_ppe=required_ppe_list,
            face_encoding=face_encoding.tolist(),  # Convert numpy to list
            face_photo_valid=True,
            created_by=request.user if request.user.is_authenticated else None
        )

        # Add to face recognition model
        success = FaceRecognitionService.add_worker_to_model(worker_id, face_encoding)

        if not success:
            logger.warning(f"Worker created but not added to face model: {worker_id}")

        return Response({
            'message': 'Worker added successfully',
            'worker_id': worker_id,
            'name': worker.name,
            'face_encoding_stored': True
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error adding worker: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retrain_face_model(request):
    """
    Retrain face recognition model with all workers in database.

    POST /api/workers/retrain-face-model/
    """
    from detection.services.face_recognition import FaceRecognitionService
    import numpy as np

    try:
        # Load all workers with valid face encodings
        workers = Worker.objects.filter(face_photo_valid=True)

        if workers.count() == 0:
            return Response({
                'error': 'No workers with valid photos found'
            }, status=status.HTTP_400_BAD_REQUEST)

        workers_data = []
        for worker in workers:
            if worker.face_encoding:
                workers_data.append({
                    'worker_id': worker.worker_id,
                    'face_encoding': np.array(worker.face_encoding)
                })

        if not workers_data:
            return Response({
                'error': 'No workers with face encodings found'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Retrain model
        success = FaceRecognitionService.retrain_from_workers(workers_data)

        if success:
            return Response({
                'message': f'Model retrained with {len(workers_data)} workers'
            })
        else:
            return Response({
                'error': 'Failed to retrain model'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f"Error retraining model: {e}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


_SEVERITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_compliance(request, worker_id):
    """
    F4 — Per-worker compliance score + streak.
    GET /api/workers/{worker_id}/compliance/
    """
    from datetime import timedelta
    from django.utils import timezone
    from detection.models import ViolationRecord

    qs = ViolationRecord.objects.filter(worker_id=worker_id)
    total = qs.count()
    resolved = qs.filter(status__in=['resolved', 'dismissed']).count()
    last = qs.order_by('-timestamp').first()
    last_ts = last.timestamp if last else None
    streak_days = (timezone.now() - last_ts).days if last_ts else None
    recent = qs.filter(timestamp__gte=timezone.now() - timedelta(days=30)).count()
    score = max(0, 100 - recent * 10)
    return Response({
        'worker_id': worker_id,
        'streak_days': streak_days,
        'score': score,
        'total_violations': total,
        'resolved_ratio': round(resolved / total, 2) if total else 1.0,
        'last_violation': last_ts.isoformat() if last_ts else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_risk(request):
    """
    F7 — Repeat-offender risk ranking.
    GET /api/workers/risk/   (weighted by count, severity, recency over 30 days)
    """
    from datetime import timedelta
    from django.utils import timezone
    from detection.models import ViolationRecord

    since = timezone.now() - timedelta(days=30)
    rows = []
    for w in Worker.objects.filter(is_active=True):
        vs = ViolationRecord.objects.filter(worker_id=w.worker_id, timestamp__gte=since)
        score = 0
        for v in vs:
            weight = _SEVERITY_WEIGHT.get(v.severity, 1)
            # recency multiplier: more recent counts more (1.0 .. 2.0)
            age_days = max(0, (timezone.now() - v.timestamp).days)
            recency = 1 + max(0.0, (30 - age_days) / 30)
            score += weight * recency
        rows.append({
            'worker_id': w.worker_id,
            'name': w.name,
            'department': w.department,
            'violations_30d': vs.count(),
            'risk_score': round(score, 1),
            'training_assigned': w.training_assigned,
        })
    rows.sort(key=lambda r: r['risk_score'], reverse=True)
    return Response({'results': rows})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def worker_training(request, worker_id):
    """
    F7 — Toggle/set the training-assigned flag.
    PATCH /api/workers/{worker_id}/training/   body: {"training_assigned": true}
    """
    worker = get_object_or_404(Worker, worker_id=worker_id)
    worker.training_assigned = bool(request.data.get('training_assigned', True))
    worker.save(update_fields=['training_assigned'])
    return Response({
        'worker_id': worker.worker_id,
        'training_assigned': worker.training_assigned,
    })