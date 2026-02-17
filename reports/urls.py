"""
URL configuration for Reports app.
"""
from django.urls import path
from .views import (
    summary_stats,
    violation_report,
    compliance_report,
    worker_report,
    export_report,
    generated_reports
)

urlpatterns = [
    # Report endpoints
    path('summary/', summary_stats, name='summary-stats'),
    path('violations/', violation_report, name='violation-report'),
    path('compliance/', compliance_report, name='compliance-report'),
    path('worker/', worker_report, name='worker-report'),
    path('export/', export_report, name='export-report'),
    path('generated/', generated_reports, name='generated-reports'),
]
