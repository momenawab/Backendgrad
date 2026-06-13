"""
F5 — Firebase Cloud Messaging push notifications.

All functions degrade gracefully: if `firebase-admin` isn't installed or
`FCM_CREDENTIALS` isn't configured, they log-and-skip (no crash). The real-time
`/ws/notifications/` WebSocket remains the primary channel regardless.
"""
import logging
from django.conf import settings

logger = logging.getLogger('detection')

_app = None
_init_failed = False


def _get_app():
    """Lazily initialise the Firebase Admin app from FCM_CREDENTIALS."""
    global _app, _init_failed
    if _app is not None or _init_failed:
        return _app
    cred_path = getattr(settings, 'FCM_CREDENTIALS', '') or ''
    if not cred_path:
        _init_failed = True
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        _app = firebase_admin.initialize_app(credentials.Certificate(cred_path))
        return _app
    except Exception as e:
        logger.info(f"FCM not configured ({e}); skipping push.")
        _init_failed = True
        return None


def _token_for_worker(worker_id):
    if not worker_id:
        return None
    try:
        from authentication.models import WorkerAccount
        acct = WorkerAccount.objects.filter(
            worker__worker_id=worker_id, enable_notifications=True
        ).first()
        return acct.fcm_token if acct else None
    except Exception:
        return None


def push_violation_to_worker(violation):
    """Send a push notification to the worker tied to a violation (best-effort)."""
    app = _get_app()
    if app is None:
        return
    token = _token_for_worker(getattr(violation, 'worker_id', None))
    if not token:
        return
    try:
        from firebase_admin import messaging
        missing = ', '.join(violation.missing_ppe or [])
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(
                title='PPE Violation Detected',
                body=f'Missing: {missing}' if missing else 'Safety violation detected.',
            ),
            data={'violation_id': str(violation.violation_id),
                  'severity': violation.severity or ''},
        )
        messaging.send(message)
    except Exception as e:  # pragma: no cover
        logger.warning(f"FCM send failed: {e}")
