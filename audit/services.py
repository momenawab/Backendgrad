"""
Audit helper — call `record_audit(...)` from any view performing a sensitive
action (worker create/delete, violation resolve/dismiss, alert-config changes,
settings changes, etc.). Best-effort: never raises into the caller.
"""
import logging
from .models import AuditLog

logger = logging.getLogger('django')


def record_audit(user, action, target_type=None, target_id=None, **detail):
    try:
        AuditLog.objects.create(
            user=user if (user and getattr(user, 'is_authenticated', False)) else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail or {},
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"audit record failed: {e}")
