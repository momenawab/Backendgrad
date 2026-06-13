"""
Enforcement service — the single place violations are recorded from any source
(HTTP upload or the /ws/detect/ WebSocket).

Implements F1 (de-duplication + auto-resolution + escalation support),
C1 (ignore PPE types the model can't actually detect), F14 (shift counters)
and the F3 hook (unauthorized person in a restricted zone).

Call `process_detections(...)` synchronously. The WebSocket consumer wraps it
in `database_sync_to_async`.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ..models import ViolationRecord
from .notification_service import NotificationService

logger = logging.getLogger('detection')


def detectable_ppe_types():
    """C1: only PPE types the YOLO model can actually detect count toward
    compliance. Everything else (safetyGlasses, earProtection, ...) is advisory
    and must never flag a worker as non-compliant."""
    classes = set((settings.PPE_CLASS_MAP or {}).values())
    classes.discard('person')
    return classes


def _cooldown_window():
    minutes = getattr(settings, 'VIOLATION_COOLDOWN_MINUTES', 10)
    return timedelta(minutes=minutes)


def _calculate_severity(missing_ppe):
    critical_ppe = ['hardHat', 'steelToedBoots']
    high_ppe = ['vest']
    if any(p in critical_ppe for p in missing_ppe):
        return 'critical'
    if any(p in high_ppe for p in missing_ppe):
        return 'high'
    if len(missing_ppe) >= 2:
        return 'medium'
    return 'low'


def _missing_for(detection):
    """Filtered missing-PPE list for a detection (C1 applied)."""
    detectable = detectable_ppe_types()
    return [
        p['type'] for p in detection.get('ppeStatus', [])
        if p.get('status') == 'nonCompliant' and p.get('type') in detectable
    ]


def _detected_for(detection):
    return [
        p['type'] for p in detection.get('ppeStatus', [])
        if p.get('status') == 'compliant'
    ]


def _auto_resolve_worker(worker_id):
    """F1 auto-resolution: close any open violations for a now-compliant worker."""
    if not worker_id:
        return 0
    now = timezone.now()
    qs = ViolationRecord.objects.filter(worker_id=worker_id, status='open')
    resolved = 0
    for v in qs:
        v.status = 'resolved'
        v.resolved_at = now
        v.save(update_fields=['status', 'resolved_at'])
        try:
            NotificationService.send_alert_resolved(v.violation_id, resolved_by='system')
        except Exception as e:  # pragma: no cover - notification best-effort
            logger.warning(f"resolved notify failed: {e}")
        resolved += 1
    return resolved


def _find_open_duplicate(worker_id, missing_ppe):
    """F1 de-dup: an open violation for the same worker + same missing set seen
    within the cooldown window."""
    since = timezone.now() - _cooldown_window()
    qs = ViolationRecord.objects.filter(status='open', timestamp__gte=since)
    if worker_id:
        qs = qs.filter(worker_id=worker_id)
    else:
        qs = qs.filter(worker_id__isnull=True)
    target = set(missing_ppe)
    for v in qs.order_by('-timestamp')[:25]:
        if set(v.missing_ppe or []) == target:
            return v
    return None


def _increment_shift(worker_id):
    """F14: bump today's shift violation counter for the worker."""
    if not worker_id:
        return
    try:
        from workers.models import Worker, WorkerShift
        worker = Worker.objects.filter(worker_id=worker_id).first()
        if not worker:
            return
        shift, _ = WorkerShift.objects.get_or_create(
            worker=worker,
            date=timezone.now().date(),
            defaults={'shift_type': getattr(worker, 'shift', 'day') or 'day'},
        )
        shift.violations_count = (shift.violations_count or 0) + 1
        shift.save(update_fields=['violations_count'])
    except Exception as e:  # pragma: no cover
        logger.warning(f"shift increment failed for {worker_id}: {e}")


def _maybe_push(violation):
    """F5 hook — push an FCM notification if the service is configured.
    Safe no-op if firebase isn't set up."""
    try:
        from .fcm_service import push_violation_to_worker
        push_violation_to_worker(violation)
    except Exception:
        pass


def _raise_security_alert(detection, camera_id):
    """F3: unknown face in a restricted zone."""
    try:
        from alerts.models import AlertHistory
        AlertHistory.objects.create(
            alert_id=str(uuid.uuid4()),
            alert_type='push',
            destination='security',
            subject='Unauthorized person detected',
            message=f'Unrecognized person detected in restricted zone '
                    f'(camera {camera_id}).',
            severity='high',
            status='sent',
            sent_at=timezone.now(),
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"security AlertHistory failed: {e}")
    try:
        NotificationService.send_system_alert(
            f'Unauthorized person detected in restricted zone (camera {camera_id}).',
            alert_type='security',
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"security WS alert failed: {e}")


def process_detections(detections, *, image=None, session_id=None,
                       camera_id=None, required_ppe=None, is_restricted=False):
    """
    Apply enforcement to a frame's detections. Returns a summary dict.

    - compliant person  -> auto-resolve that worker's open violations
    - non-compliant     -> de-dup, else create a violation (+ notify/shift/push)
    - unknown in a restricted zone -> security alert (F3)
    """
    created, resolved, security = [], 0, 0
    now = timezone.now()

    for det in detections or []:
        worker_id = det.get('workerId')
        overall = det.get('overallStatus')

        if overall == 'compliant':
            resolved += _auto_resolve_worker(worker_id)
            continue

        missing = _missing_for(det)
        if not missing:
            # Only undetectable PPE was "missing" (C1) -> treat as compliant.
            resolved += _auto_resolve_worker(worker_id)
            continue

        # F3: unauthorized person in a restricted area.
        if is_restricted and not worker_id:
            _raise_security_alert(det, camera_id)
            security += 1

        # F1 de-dup.
        dup = _find_open_duplicate(worker_id, missing)
        if dup:
            dup.last_seen = now
            dup.save(update_fields=['last_seen'])
            continue

        worker_name = det.get('workerName') or worker_id or 'Unknown Worker'
        if worker_id:
            try:
                from workers.models import Worker
                w = Worker.objects.filter(worker_id=worker_id).first()
                if w:
                    worker_name = w.name
            except Exception:
                pass

        kwargs = dict(
            violation_id=str(uuid.uuid4()),
            worker_id=worker_id,
            worker_name=worker_name,
            missing_ppe=missing,
            detected_ppe=_detected_for(det),
            bounding_box=det.get('boundingBox') or {},
            severity=_calculate_severity(missing),
            last_seen=now,
        )
        if image is not None:
            kwargs['image'] = image
        violation = ViolationRecord.objects.create(**kwargs)
        created.append(violation)

        # Notify (new violation only), bump shift, push.
        try:
            NotificationService.send_violation_notification({
                'worker_id': worker_id,
                'worker_name': worker_name,
                'missing_ppe': missing,
                'required_ppe': required_ppe or [],
                'timestamp': None,
            })
        except Exception as e:  # pragma: no cover
            logger.warning(f"violation notify failed: {e}")
        _increment_shift(worker_id)
        _maybe_push(violation)

    return {'created': created, 'resolved': resolved, 'security': security}


def find_overdue_open_violations(threshold_minutes):
    """Open violations whose last activity is older than the threshold (F1 escalation)."""
    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
    return ViolationRecord.objects.filter(status='open', timestamp__lte=cutoff)
