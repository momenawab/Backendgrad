"""
URL configuration for Workers app.
"""
from django.urls import path
from .views import (
    WorkerListCreateView,
    WorkerDetailView,
    WorkerByWorkerIdView,
    worker_stats,
    worker_shifts,
    worker_violations,
    worker_violations_summary,
    add_worker_with_photo,
    retrain_face_model,
    worker_compliance,
    worker_risk,
    worker_training,
)

urlpatterns = [
    # Worker CRUD
    path('', WorkerListCreateView.as_view(), name='worker-list-create'),
    path('<int:id>/', WorkerDetailView.as_view(), name='worker-detail'),
    path('id/<str:worker_id>/', WorkerByWorkerIdView.as_view(), name='worker-by-worker-id'),

    # Worker statistics and related data
    path('stats/', worker_stats, name='worker-stats'),
    path('risk/', worker_risk, name='worker-risk'),
    path('violations-summary/', worker_violations_summary, name='worker-violations-summary'),
    path('<str:worker_id>/shifts/', worker_shifts, name='worker-shifts'),
    path('<str:worker_id>/violations/', worker_violations, name='worker-violations'),
    path('<str:worker_id>/compliance/', worker_compliance, name='worker-compliance'),
    path('<str:worker_id>/training/', worker_training, name='worker-training'),

    # Face recognition endpoints
    path('add-with-photo/', add_worker_with_photo, name='worker-add-with-photo'),
    path('retrain-face-model/', retrain_face_model, name='retrain-face-model'),
]
