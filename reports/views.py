"""
Views for Reports app.
"""
import logging
import uuid
import csv
import json
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncHour
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from detection.models import DetectionRecord, ViolationRecord, DetectionSession
from workers.models import Worker
from .models import GeneratedReport, ReportSchedule
from .serializers import ReportRequestSerializer, GeneratedReportSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def summary_stats(request):
    """
    Get safety summary statistics.

    GET /api/reports/summary/

    Query params:
        start_date: Start date for statistics (default: 30 days ago)
        end_date: End date for statistics (default: now)
        department: Filter by department
    """
    # Get date range
    end_date = request.query_params.get('end_date')
    start_date = request.query_params.get('start_date')

    if end_date:
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_date = timezone.now()

    if start_date:
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        start_date = end_date - timedelta(days=30)

    # Base querysets
    detections_qs = DetectionRecord.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    )
    violations_qs = ViolationRecord.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    )

    # Department filter
    department = request.query_params.get('department')
    if department:
        # Filter violations by worker department
        worker_ids = Worker.objects.filter(department=department).values_list('worker_id', flat=True)
        violations_qs = violations_qs.filter(worker_id__in=worker_ids)

    # Calculate stats
    total_detections = detections_qs.count()
    total_violations = violations_qs.count()

    # Detection stats
    total_people_detected = detections_qs.aggregate(total=Sum('detected_count'))['total'] or 0
    total_compliant = detections_qs.aggregate(total=Sum('compliant_count'))['total'] or 0
    total_non_compliant = detections_qs.aggregate(total=Sum('non_compliant_count'))['total'] or 0

    # Violation stats by severity
    severity_breakdown = violations_qs.values('severity').annotate(
        count=Count('id')
    )

    # Violation stats by status
    status_breakdown = violations_qs.values('status').annotate(
        count=Count('id')
    )

    # Top violation types
    violation_types = {}
    for violation in violations_qs:
        for ppe_type in violation.missing_ppe:
            violation_types[ppe_type] = violation_types.get(ppe_type, 0) + 1

    top_violations = sorted(violation_types.items(), key=lambda x: x[1], reverse=True)[:5]

    # Workers with most violations
    top_workers = violations_qs.values('worker_id', 'worker_name').annotate(
        violation_count=Count('id')
    ).order_by('-violation_count')[:10]

    # Compliance rate
    if total_people_detected > 0:
        compliance_rate = round((total_compliant / total_people_detected) * 100, 2)
    else:
        compliance_rate = 100.0

    # Daily trend (last 30 days)
    daily_stats = detections_qs.annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        detections=Count('id'),
        compliant=Sum('compliant_count'),
        non_compliant=Sum('non_compliant_count')
    ).order_by('date')

    return Response({
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': (end_date - start_date).days
        },
        'overview': {
            'total_detections': total_detections,
            'total_violations': total_violations,
            'total_people_detected': total_people_detected,
            'compliance_rate': compliance_rate
        },
        'detection_stats': {
            'compliant': total_compliant,
            'non_compliant': total_non_compliant
        },
        'violation_breakdown': {
            'by_severity': list(severity_breakdown),
            'by_status': list(status_breakdown),
            'top_violation_types': [{'type': k, 'count': v} for k, v in top_violations]
        },
        'top_workers': list(top_workers),
        'daily_trend': list(daily_stats)
    })


from django.db.models import Sum


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def violation_report(request):
    """
    Get detailed violation records with filters.

    GET /api/reports/violations/

    Query params:
        start_date: Start date filter
        end_date: End date filter
        severity: Severity filter
        status: Status filter
        worker_id: Worker ID filter
        department: Department filter
        page: Page number
        page_size: Items per page
    """
    queryset = ViolationRecord.objects.all()

    # Apply filters
    start_date = request.query_params.get('start_date')
    if start_date:
        queryset = queryset.filter(timestamp__gte=start_date)

    end_date = request.query_params.get('end_date')
    if end_date:
        queryset = queryset.filter(timestamp__lte=end_date)

    severity = request.query_params.get('severity')
    if severity:
        queryset = queryset.filter(severity=severity)

    status = request.query_params.get('status')
    if status:
        queryset = queryset.filter(status=status)

    worker_id = request.query_params.get('worker_id')
    if worker_id:
        queryset = queryset.filter(worker_id=worker_id)

    department = request.query_params.get('department')
    if department:
        worker_ids = Worker.objects.filter(department=department).values_list('worker_id', flat=True)
        queryset = queryset.filter(worker_id__in=worker_ids)

    # Order by most recent
    queryset = queryset.order_by('-timestamp')

    # Paginate
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size

    records = queryset[start:end]
    total = queryset.count()

    # Format results
    results = []
    for record in records:
        results.append({
            'violation_id': record.violation_id,
            'timestamp': record.timestamp.isoformat(),
            'worker_id': record.worker_id,
            'worker_name': record.worker_name,
            'missing_ppe': record.missing_ppe,
            'detected_ppe': record.detected_ppe,
            'severity': record.severity,
            'status': record.status,
            'image_url': record.image.url if record.image else None
        })

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': results
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_report(request):
    """
    Get compliance metrics and trends.

    GET /api/reports/compliance/

    Query params:
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)
        group_by: Group by 'day', 'week', or 'department'
    """
    # Get date range
    end_date = request.query_params.get('end_date')
    start_date = request.query_params.get('start_date')
    group_by = request.query_params.get('group_by', 'day')

    if end_date:
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_date = timezone.now()

    if start_date:
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        start_date = end_date - timedelta(days=30)

    detections_qs = DetectionRecord.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    )

    # Overall compliance
    total_detected = detections_qs.aggregate(total=Sum('detected_count'))['total'] or 0
    total_compliant = detections_qs.aggregate(total=Sum('compliant_count'))['total'] or 0

    if total_detected > 0:
        overall_compliance = round((total_compliant / total_detected) * 100, 2)
    else:
        overall_compliance = 100.0

    # Group data
    if group_by == 'day':
        grouped = detections_qs.annotate(
            period=TruncDate('timestamp')
        ).values('period').annotate(
            detected=Sum('detected_count'),
            compliant=Sum('compliant_count'),
            non_compliant=Sum('non_compliant_count')
        ).order_by('period')

    elif group_by == 'department':
        # Group by worker department
        grouped = []
        departments = Worker.objects.values_list('department', flat=True).distinct()

        for dept in departments:
            if not dept:
                continue
            worker_ids = Worker.objects.filter(department=dept).values_list('worker_id', flat=True)

            # Get detections for workers in this department
            dept_detections = detections_qs.filter(
                session_id__in=DetectionSession.objects.filter(
                    # This is a simplified approach - in production, you'd track department per session
                )
            )

            # For now, return aggregated stats per department using violation data
            dept_violations = ViolationRecord.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                worker_id__in=worker_ids
            )

            dept_detected = dept_violations.count() * 2  # Rough estimate
            dept_compliant = dept_detected - dept_violations.count()

            if dept_detected > 0:
                grouped.append({
                    'period': dept,
                    'detected': dept_detected,
                    'compliant': dept_compliant,
                    'non_compliant': dept_violations.count()
                })

    else:
        # Default to daily
        grouped = detections_qs.annotate(
            period=TruncDate('timestamp')
        ).values('period').annotate(
            detected=Sum('detected_count'),
            compliant=Sum('compliant_count'),
            non_compliant=Sum('non_compliant_count')
        ).order_by('period')

    # Calculate compliance rate per group
    for item in grouped:
        if item['detected'] and item['detected'] > 0:
            item['compliance_rate'] = round((item['compliant'] / item['detected']) * 100, 2)
        else:
            item['compliance_rate'] = 100.0

    return Response({
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'overall_compliance': overall_compliance,
        'grouped_data': list(grouped),
        'group_by': group_by
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_report(request):
    """
    Get worker-specific compliance report.

    GET /api/reports/worker/

    Query params:
        worker_id: Specific worker ID (optional, returns all if not specified)
        start_date: Start date
        end_date: End date
    """
    worker_id = request.query_params.get('worker_id')

    if worker_id:
        # Single worker report
        worker = Worker.objects.filter(worker_id=worker_id).first()
        if not worker:
            return Response({'error': 'Worker not found'}, status=404)

        violations = ViolationRecord.objects.filter(worker_id=worker_id).order_by('-timestamp')
        total_violations = violations.count()
        resolved = violations.filter(status='resolved').count()

        return Response({
            'worker': {
                'worker_id': worker.worker_id,
                'name': worker.name,
                'department': worker.department,
                'position': worker.position,
                'required_ppe': worker.required_ppe
            },
            'stats': {
                'total_violations': total_violations,
                'resolved_violations': resolved,
                'open_violations': total_violations - resolved,
                'compliance_rate': worker.compliance_rate
            },
            'recent_violations': [
                {
                    'violation_id': v.violation_id,
                    'timestamp': v.timestamp.isoformat(),
                    'missing_ppe': v.missing_ppe,
                    'severity': v.severity,
                    'status': v.status
                }
                for v in violations[:10]
            ]
        })
    else:
        # All workers summary
        workers = Worker.objects.filter(is_active=True)
        results = []

        for worker in workers:
            violations = ViolationRecord.objects.filter(worker_id=worker.worker_id)
            total = violations.count()
            resolved = violations.filter(status='resolved').count()

            results.append({
                'worker_id': worker.worker_id,
                'name': worker.name,
                'department': worker.department,
                'total_violations': total,
                'resolved_violations': resolved,
                'compliance_rate': worker.compliance_rate
            })

        # Sort by violations count
        results.sort(key=lambda x: x['total_violations'], reverse=True)

        return Response({
            'workers': results[:50],  # Top 50
            'total_workers': len(results)
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_report(request):
    """
    Generate and export a report.

    POST /api/reports/export/

    Body:
        report_type: summary|violations|compliance|worker
        format: csv|json
        start_date: ISO date string (optional)
        end_date: ISO date string (optional)
        department: department filter (optional)
        worker_id: worker filter (optional)
    """
    serializer = ReportRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    report_type = serializer.validated_data['report_type']
    report_format = serializer.validated_data['format']
    start_date = serializer.validated_data.get('start_date')
    end_date = serializer.validated_data.get('end_date')
    department = serializer.validated_data.get('department')
    worker_id = serializer.validated_data.get('worker_id')

    # Create generated report record
    report = GeneratedReport.objects.create(
        report_id=f"report_{uuid.uuid4().hex[:12]}",
        title=f"{report_type.title()} Report",
        report_type=report_type,
        format=report_format,
        parameters=serializer.validated_data,
        generated_by=request.user
    )

    # Generate report data based on type
    if report_type == 'violations':
        data = _get_violation_data(start_date, end_date, department, worker_id)
    elif report_type == 'compliance':
        data = _get_compliance_data(start_date, end_date, department)
    elif report_type == 'worker':
        data = _get_worker_data(worker_id)
    else:
        data = _get_summary_data(start_date, end_date, department)

    # Format response
    if report_format == 'csv':
        response = _generate_csv_response(data, report_type)
        report.status = 'completed'
        report.completed_at = timezone.now()
        report.save()
        return response
    else:  # JSON
        report.status = 'completed'
        report.completed_at = timezone.now()
        report.save()
        return Response(data)


def _get_summary_data(start_date, end_date, department):
    """Get summary report data."""
    detections = DetectionRecord.objects.all()
    violations = ViolationRecord.objects.all()

    if start_date:
        detections = detections.filter(timestamp__gte=start_date)
        violations = violations.filter(timestamp__gte=start_date)
    if end_date:
        detections = detections.filter(timestamp__lte=end_date)
        violations = violations.filter(timestamp__lte=end_date)
    if department:
        worker_ids = Worker.objects.filter(department=department).values_list('worker_id', flat=True)
        violations = violations.filter(worker_id__in=worker_ids)

    return {
        'total_detections': detections.count(),
        'total_violations': violations.count(),
        'violations_by_severity': list(violations.values('severity').annotate(count=Count('id')))
    }


def _get_violation_data(start_date, end_date, department, worker_id):
    """Get violation report data."""
    violations = ViolationRecord.objects.all()

    if start_date:
        violations = violations.filter(timestamp__gte=start_date)
    if end_date:
        violations = violations.filter(timestamp__lte=end_date)
    if department:
        worker_ids = Worker.objects.filter(department=department).values_list('worker_id', flat=True)
        violations = violations.filter(worker_id__in=worker_ids)
    if worker_id:
        violations = violations.filter(worker_id=worker_id)

    return list(violations.values(
        'violation_id', 'timestamp', 'worker_id', 'worker_name',
        'missing_ppe', 'severity', 'status'
    ))


def _get_compliance_data(start_date, end_date, department):
    """Get compliance report data."""
    detections = DetectionRecord.objects.all()

    if start_date:
        detections = detections.filter(timestamp__gte=start_date)
    if end_date:
        detections = detections.filter(timestamp__lte=end_date)

    daily = detections.annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        detected=Sum('detected_count'),
        compliant=Sum('compliant_count')
    ).order_by('date')

    return list(daily)


def _get_worker_data(worker_id):
    """Get worker report data."""
    if worker_id:
        workers = Worker.objects.filter(worker_id=worker_id)
    else:
        workers = Worker.objects.filter(is_active=True)

    return list(workers.values(
        'worker_id', 'name', 'department', 'position',
        'required_ppe', 'is_active'
    ))


def _generate_csv_response(data, report_type):
    """Generate CSV response from data."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'

    writer = csv.writer(response)

    if report_type == 'violations' and data:
        writer.writerow(['Violation ID', 'Timestamp', 'Worker ID', 'Worker Name',
                        'Missing PPE', 'Severity', 'Status'])
        for row in data:
            writer.writerow([
                row['violation_id'],
                row['timestamp'],
                row['worker_id'],
                row['worker_name'],
                str(row['missing_ppe']),
                row['severity'],
                row['status']
            ])

    elif report_type == 'worker' and data:
        writer.writerow(['Worker ID', 'Name', 'Department', 'Position',
                        'Required PPE', 'Active'])
        for row in data:
            writer.writerow([
                row['worker_id'],
                row['name'],
                row['department'],
                row['position'],
                str(row['required_ppe']),
                row['is_active']
            ])

    else:
        writer.writerow(['Key', 'Value'])
        for key, value in data.items():
            writer.writerow([key, str(value)])

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generated_reports(request):
    """
    Get list of generated reports.

    GET /api/reports/generated/
    """
    reports = GeneratedReport.objects.order_by('-created_at')[:50]
    serializer = GeneratedReportSerializer(
        reports,
        many=True,
        context={'request': request}
    )
    return Response(serializer.data)
