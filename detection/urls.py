"""
URL configuration for Detection app.
"""
from django.urls import path
from .views import (
    upload_and_detect,
    detection_records,
    violation_records,
    violation_detail,
    create_session,
    end_session,
    session_list,
    session_detail,
    health_check
)

urlpatterns = [
    # Detection endpoints
    path('upload/', upload_and_detect, name='upload-and-detect'),
    path('records/', detection_records, name='detection-records'),
    path('health/', health_check, name='health-check'),

    # Violation endpoints
    path('violations/', violation_records, name='violation-records'),
    path('violations/<str:violation_id>/', violation_detail, name='violation-detail'),

    # Session endpoints
    path('sessions/', session_list, name='session-list'),
    path('sessions/create/', create_session, name='create-session'),
    path('sessions/<str:session_id>/', session_detail, name='session-detail'),
    path('sessions/<str:session_id>/end/', end_session, name='end-session'),
]
