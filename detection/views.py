"""
Views for Detection app.
"""
import logging
import uuid
from datetime import datetime
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import DetectionRecord, ViolationRecord, DetectionSession
from .serializers import (
    DetectionRecordSerializer,
    ViolationRecordSerializer,
    ViolationRecordUpdateSerializer,
    DetectionSessionSerializer,
    ImageUploadSerializer
)
from .services import PPEModelService

logger = logging.getLogger('detection')


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def upload_and_detect(request):
    """
    Upload an image for PPE detection.

    POST /api/detection/upload/
    Content-Type: multipart/form-data

    Body:
        image: file (required)
        session_id: string (optional)
        required_ppe: array of strings (optional)
        confidence_threshold: float (optional)

    Returns:
        DetectionResult JSON with detections and compliance status
    """
    try:
        # Validate input
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data['image']
        session_id = serializer.validated_data.get('session_id')
        required_ppe = serializer.validated_data.get('required_ppe')
        conf_threshold = serializer.validated_data.get('confidence_threshold')

        # Set defaults
        if required_ppe is None:
            required_ppe = ['hardHat', 'vest', 'gloves', 'steelToedBoots']

        # Read image bytes
        image_bytes = image_file.read()

        # Run PPE detection
        result = PPEModelService.predict_from_bytes(
            image_bytes=image_bytes,
            conf_threshold=conf_threshold,
            required_ppe=required_ppe
        )

        # Save detection record
        detection_record = DetectionRecord.objects.create(
            frame_id=result.frameId,
            detected_count=result.detected,
            compliant_count=result.compliant,
            non_compliant_count=result.nonCompliant,
            detections=result.detections,
            session_id=session_id
        )

        # Save image if violations detected
        if result.nonCompliant > 0:
            # Generate filename and save
            filename = f"detection_{result.frameId}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            # In production, save to media storage
            # detection_record.image_path = f"media/detections/{filename}"

        # Check for violations and create violation records
        violations_created = []
        for detection in result.detections:
            if detection['overallStatus'] != 'compliant':
                # Get missing PPE
                missing_ppe = [
                    ppe['type'] for ppe in detection['ppeStatus']
                    if ppe['status'] == 'nonCompliant'
                ]

                # Get detected PPE
                detected_ppe = [
                    ppe['type'] for ppe in detection['ppeStatus']
                    if ppe['status'] == 'compliant'
                ]

                # Create violation record (with image if available)
                # For now, we'll create it without storing the full image
                # to avoid storage issues. In production, store the image.
                violation = ViolationRecord.objects.create(
                    violation_id=str(uuid.uuid4()),
                    worker_id=detection.get('workerId'),
                    worker_name=detection.get('workerId'),  # Would be filled by face recognition
                    missing_ppe=missing_ppe,
                    detected_ppe=detected_ppe,
                    image=image_file,  # Store the uploaded image
                    bounding_box=detection['boundingBox'],
                    severity=_calculate_severity(missing_ppe)
                )
                violations_created.append(ViolationRecordSerializer(
                    violation,
                    context={'request': request}
                ).data)

        # Return detection result
        response_data = result.to_dict()
        response_data['record_id'] = detection_record.id
        response_data['violations'] = violations_created

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in upload_and_detect: {e}")
        return Response({
            'error': 'Detection failed',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detection_records(request):
    """
    Get detection records with optional filtering.

    GET /api/detection/records/

    Query params:
        session_id: Filter by session ID
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
    """
    queryset = DetectionRecord.objects.all()

    # Apply filters
    session_id = request.query_params.get('session_id')
    if session_id:
        queryset = queryset.filter(session_id=session_id)

    start_date = request.query_params.get('start_date')
    if start_date:
        queryset = queryset.filter(timestamp__gte=start_date)

    end_date = request.query_params.get('end_date')
    if end_date:
        queryset = queryset.filter(timestamp__lte=end_date)

    # Paginate results
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('page_size', 20)

    start = (int(page) - 1) * int(page_size)
    end = start + int(page_size)

    records = queryset.all()[start:end]
    total = queryset.count()

    return Response({
        'count': total,
        'page': int(page),
        'page_size': int(page_size),
        'results': DetectionRecordSerializer(records, many=True).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def violation_records(request):
    """
    Get violation records with optional filtering.

    GET /api/detection/violations/

    Query params:
        worker_id: Filter by worker ID
        status: Filter by status (open, reviewed, resolved, dismissed)
        severity: Filter by severity
        start_date: Filter by start date
        end_date: Filter by end date
    """
    queryset = ViolationRecord.objects.all()

    # Apply filters
    worker_id = request.query_params.get('worker_id')
    if worker_id:
        queryset = queryset.filter(worker_id=worker_id)

    violation_status = request.query_params.get('status')
    if violation_status:
        queryset = queryset.filter(status=violation_status)

    severity = request.query_params.get('severity')
    if severity:
        queryset = queryset.filter(severity=severity)

    start_date = request.query_params.get('start_date')
    if start_date:
        queryset = queryset.filter(timestamp__gte=start_date)

    end_date = request.query_params.get('end_date')
    if end_date:
        queryset = queryset.filter(timestamp__lte=end_date)

    # Order by most recent
    queryset = queryset.order_by('-timestamp')

    # Paginate
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('page_size', 20)

    start = (int(page) - 1) * int(page_size)
    end = start + int(page_size)

    records = queryset.all()[start:end]
    total = queryset.count()

    return Response({
        'count': total,
        'page': int(page),
        'page_size': int(page_size),
        'results': ViolationRecordSerializer(
            records,
            many=True,
            context={'request': request}
        ).data
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def violation_detail(request, violation_id):
    """
    Get or update a specific violation record.

    GET /api/detection/violations/{violation_id}/
    PUT /api/detection/violations/{violation_id}/
    """
    violation = get_object_or_404(ViolationRecord, violation_id=violation_id)

    if request.method == 'GET':
        return Response(ViolationRecordSerializer(
            violation,
            context={'request': request}
        ).data)

    elif request.method == 'PUT':
        serializer = ViolationRecordUpdateSerializer(
            violation,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # If resolved, set resolved_by and resolved_at
        if serializer.validated_data.get('status') == 'resolved':
            violation.resolved_by = request.user
            violation.resolved_at = datetime.now()
            violation.save()

        return Response(ViolationRecordSerializer(
            violation,
            context={'request': request}
        ).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_session(request):
    """
    Create a new detection session.

    POST /api/detection/sessions/

    Body:
        location: string (optional)
        camera_id: string (optional)
    """
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    session = DetectionSession.objects.create(
        session_id=session_id,
        location=request.data.get('location'),
        camera_id=request.data.get('camera_id'),
        started_by=request.user
    )

    return Response(DetectionSessionSerializer(session).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_session(request, session_id):
    """
    End a detection session.

    POST /api/detection/sessions/{session_id}/end/
    """
    session = get_object_or_404(DetectionSession, session_id=session_id)
    session.status = 'completed'
    session.end_time = datetime.now()
    session.save()

    return Response(DetectionSessionSerializer(session).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_list(request):
    """
    Get list of detection sessions.

    GET /api/detection/sessions/
    """
    sessions = DetectionSession.objects.order_by('-start_time')[:50]
    return Response(DetectionSessionSerializer(sessions, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    """
    Get details of a specific session.

    GET /api/detection/sessions/{session_id}/
    """
    session = get_object_or_404(DetectionSession, session_id=session_id)
    return Response(DetectionSessionSerializer(session).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for detection service.

    GET /api/detection/health/
    """
    model_loaded = PPEModelService._model_loaded

    return Response({
        'status': 'healthy',
        'model_loaded': model_loaded,
        'model_path': getattr(settings, 'PPE_MODEL_PATH', 'Not configured')
    })


def _calculate_severity(missing_ppe):
    """
    Calculate severity level based on missing PPE.

    Args:
        missing_ppe: List of missing PPE types

    Returns:
        Severity level string
    """
    critical_ppe = ['hardHat', 'steelToedBoots']
    high_ppe = ['vest']

    if any(ppe in critical_ppe for ppe in missing_ppe):
        return 'critical'
    elif any(ppe in high_ppe for ppe in missing_ppe):
        return 'high'
    elif len(missing_ppe) >= 2:
        return 'medium'
    else:
        return 'low'
