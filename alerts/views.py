"""
Views for Alerts app.
"""
import logging
import uuid
from datetime import datetime
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import AlertConfig, AlertHistory, AlertRecipient
from .serializers import (
    AlertConfigSerializer,
    AlertConfigCreateSerializer,
    AlertHistorySerializer,
    AlertRecipientSerializer,
    AlertRecipientCreateSerializer,
    TestAlertSerializer
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_config_list(request):
    """
    Get all alert configurations.

    GET /api/alerts/config/
    """
    configs = AlertConfig.objects.all()
    serializer = AlertConfigSerializer(configs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def alert_config_create(request):
    """
    Create a new alert configuration.

    POST /api/alerts/config/
    """
    serializer = AlertConfigCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config = serializer.save(created_by=request.user)
    return Response(
        AlertConfigSerializer(config).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def alert_config_detail(request, config_id):
    """
    Get, update or delete a specific alert configuration.

    GET /api/alerts/config/{config_id}/
    PUT /api/alerts/config/{config_id}/
    DELETE /api/alerts/config/{config_id}/
    """
    config = get_object_or_404(AlertConfig, id=config_id)

    if request.method == 'GET':
        return Response(AlertConfigSerializer(config).data)

    elif request.method == 'PUT':
        serializer = AlertConfigCreateSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AlertConfigSerializer(config).data)

    elif request.method == 'DELETE':
        config.delete()
        return Response({'message': 'Alert configuration deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_history(request):
    """
    Get alert history with optional filtering.

    GET /api/alerts/history/

    Query params:
        status: Filter by status (pending, sent, failed, retrying)
        severity: Filter by severity
        alert_type: Filter by alert type
        start_date: Filter by start date
        end_date: Filter by end date
    """
    queryset = AlertHistory.objects.all()

    # Apply filters
    alert_status = request.query_params.get('status')
    if alert_status:
        queryset = queryset.filter(status=alert_status)

    severity = request.query_params.get('severity')
    if severity:
        queryset = queryset.filter(severity=severity)

    alert_type = request.query_params.get('alert_type')
    if alert_type:
        queryset = queryset.filter(alert_type=alert_type)

    start_date = request.query_params.get('start_date')
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)

    end_date = request.query_params.get('end_date')
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)

    # Order by most recent
    queryset = queryset.order_by('-created_at')

    # Paginate
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size

    records = queryset[start:end]
    total = queryset.count()

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': AlertHistorySerializer(records, many=True).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_stats(request):
    """
    Get alert statistics.

    GET /api/alerts/stats/
    """
    total_alerts = AlertHistory.objects.count()
    sent_alerts = AlertHistory.objects.filter(status='sent').count()
    failed_alerts = AlertHistory.objects.filter(status='failed').count()
    pending_alerts = AlertHistory.objects.filter(status='pending').count()

    # By severity
    from django.db.models import Count
    severity_stats = AlertHistory.objects.values('severity').annotate(
        count=Count('id')
    )

    # By type
    type_stats = AlertHistory.objects.values('alert_type').annotate(
        count=Count('id')
    )

    return Response({
        'total_alerts': total_alerts,
        'sent_alerts': sent_alerts,
        'failed_alerts': failed_alerts,
        'pending_alerts': pending_alerts,
        'by_severity': list(severity_stats),
        'by_type': list(type_stats)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_alert(request):
    """
    Send a test alert.

    POST /api/alerts/test/
    """
    serializer = TestAlertSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    alert_type = serializer.validated_data['alert_type']
    destination = serializer.validated_data['destination']
    message = serializer.validated_data['message']

    # Create alert history record
    alert = AlertHistory.objects.create(
        alert_id=f"test_{uuid.uuid4().hex[:12]}",
        alert_type=alert_type,
        destination=destination,
        subject='SafeSight Test Alert',
        message=message,
        severity='low',
        status='pending',
        triggered_by=request.user
    )

    # In production, you would send the actual alert here
    # For now, just mark as sent
    alert.status = 'sent'
    alert.sent_at = datetime.now()
    alert.save()

    logger.info(f"Test alert sent to {destination} via {alert_type}")

    return Response({
        'message': 'Test alert sent successfully',
        'alert_id': alert.alert_id,
        'alert_type': alert_type,
        'destination': destination
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def recipient_list(request):
    """
    Get all recipients or create a new one.

    GET /api/alerts/recipients/
    POST /api/alerts/recipients/
    """
    if request.method == 'GET':
        recipients = AlertRecipient.objects.all()
        serializer = AlertRecipientSerializer(recipients, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = AlertRecipientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipient = serializer.save()
        return Response(
            AlertRecipientSerializer(recipient).data,
            status=status.HTTP_201_CREATED
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def recipient_detail(request, recipient_id):
    """
    Get, update or delete a specific recipient.

    GET /api/alerts/recipients/{recipient_id}/
    PUT /api/alerts/recipients/{recipient_id}/
    DELETE /api/alerts/recipients/{recipient_id}/
    """
    recipient = get_object_or_404(AlertRecipient, id=recipient_id)

    if request.method == 'GET':
        return Response(AlertRecipientSerializer(recipient).data)

    elif request.method == 'PUT':
        serializer = AlertRecipientCreateSerializer(
            recipient,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AlertRecipientSerializer(recipient).data)

    elif request.method == 'DELETE':
        recipient.delete()
        return Response({'message': 'Recipient deleted successfully'})
