"""
F1 escalation — run on a schedule (cron):

    */5 * * * *  cd /home/ubuntu/safesight-backend && venv/bin/python manage.py escalate_violations

Finds violations that are still `open` past the escalation threshold and sends a
single escalation alert per violation (marked via `alert_sent`) to supervisors.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from detection.services.enforcement import find_overdue_open_violations
from detection.services.notification_service import NotificationService


class Command(BaseCommand):
    help = "Escalate PPE violations that have stayed open past the threshold."

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes', type=int,
            default=getattr(settings, 'VIOLATION_ESCALATION_MINUTES', 30),
            help='Age (minutes) after which an open violation is escalated.',
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        overdue = find_overdue_open_violations(minutes).filter(alert_sent=False)
        count = 0
        for v in overdue:
            worker = v.worker_name or v.worker_id or 'Unknown worker'
            try:
                NotificationService.send_system_alert(
                    f'ESCALATION: violation {v.violation_id} for {worker} '
                    f'(missing {", ".join(v.missing_ppe or [])}) has been open '
                    f'for over {minutes} minutes.',
                    alert_type='escalation',
                )
            except Exception as e:
                self.stderr.write(f'  notify failed for {v.violation_id}: {e}')
                continue
            v.alert_sent = True
            v.alert_sent_at = timezone.now()
            v.save(update_fields=['alert_sent', 'alert_sent_at'])
            count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Escalated {count} violation(s) older than {minutes} min.'
        ))
