"""
Power BI Streaming Dataset push service.

Pushes violation events to the Power BI REST API so the embedded
dashboard updates in real-time without a gateway or scheduled refresh.

Setup:
1. In Power BI Service → My Workspace → + New → Streaming dataset → API
2. Add fields: timestamp, worker_id, worker_name, missing_ppe, severity,
               violation_count, compliance_rate
3. Enable "Historic data analysis"
4. Copy the Push URL and set it in POWER_BI_PUSH_URL in Django settings.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings

logger = logging.getLogger(__name__)

# Set POWER_BI_PUSH_URL in settings.py (or .env) to enable pushing.
_PUSH_URL: str = getattr(settings, 'POWER_BI_PUSH_URL', '')


def push_violation(
    worker_id: str | None,
    worker_name: str,
    missing_ppe: list[str],
    severity: str,
    total_violations_today: int = 0,
    compliance_rate: float = 0.0,
) -> None:
    """
    Push one violation event to the Power BI streaming dataset.
    Runs in a background thread so it never blocks the API response.
    """
    if not _PUSH_URL:
        logger.debug('POWER_BI_PUSH_URL not configured — skipping push.')
        return

    payload = [
        {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'worker_id': worker_id or 'Unknown',
            'worker_name': worker_name,
            'missing_ppe': ', '.join(missing_ppe) if missing_ppe else 'None',
            'severity': severity,
            'violation_count': total_violations_today,
            'compliance_rate': round(compliance_rate, 2),
        }
    ]

    threading.Thread(target=_post, args=(payload,), daemon=True).start()


def _post(payload: list[dict]) -> None:
    body = json.dumps(payload).encode('utf-8')
    req = Request(
        _PUSH_URL,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201):
                logger.warning('Power BI push returned status %s', resp.status)
    except URLError as exc:
        logger.warning('Power BI push failed: %s', exc)
    except Exception as exc:
        logger.error('Unexpected error pushing to Power BI: %s', exc)
