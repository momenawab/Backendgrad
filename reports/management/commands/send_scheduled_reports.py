"""
F6 — send due scheduled reports. Run on a schedule (cron):

    0 7 * * *  cd /home/ubuntu/safesight-backend && venv/bin/python manage.py send_scheduled_reports

For each active ReportSchedule whose next_send is due (or null), generate the
report PDF, email it to the recipients, and advance last_sent / next_send.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports.models import ReportSchedule, GeneratedReport
from reports.views import compute_report_data
from reports.services.pdf import build_report_pdf

_FREQ_DELTA = {
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
    'monthly': timedelta(days=30),
}


class Command(BaseCommand):
    help = "Generate and email scheduled reports that are due."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Send all active schedules regardless of next_send.')

    def handle(self, *args, **options):
        now = timezone.now()
        qs = ReportSchedule.objects.filter(is_active=True)
        if not options['force']:
            from django.db.models import Q
            qs = qs.filter(Q(next_send__isnull=True) | Q(next_send__lte=now))

        sent = 0
        for sched in qs:
            try:
                data = compute_report_data(sched.report_type, **(sched.filters or {}))
                title = f"{sched.report_type.title()} Report"
                pdf = build_report_pdf(title, data)

                report = GeneratedReport.objects.create(
                    report_id=f"sched_{sched.id}_{now.strftime('%Y%m%d%H%M')}",
                    title=title, report_type=sched.report_type, format='pdf',
                    parameters=sched.filters or {}, status='completed',
                    completed_at=now, file_size=len(pdf),
                )

                recipients = [e.strip() for e in (sched.recipients or '').split(',') if e.strip()]
                if recipients:
                    msg = EmailMessage(
                        subject=f"SafeSight scheduled report: {title}",
                        body=f"Attached is your {sched.frequency} {sched.report_type} report.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=recipients,
                    )
                    msg.attach(f"{report.report_id}.pdf", pdf, 'application/pdf')
                    msg.send(fail_silently=False)

                sched.last_sent = now
                sched.next_send = now + _FREQ_DELTA.get(sched.frequency, timedelta(weeks=1))
                sched.save(update_fields=['last_sent', 'next_send'])
                sent += 1
            except Exception as e:
                self.stderr.write(f'  schedule {sched.id} failed: {e}')

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} scheduled report(s).'))
