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
    worker_violations
)

urlpatterns = [
    # Worker CRUD
    path('', WorkerListCreateView.as_view(), name='worker-list-create'),
    path('<int:id>/', WorkerDetailView.as_view(), name='worker-detail'),
    path('id/<str:worker_id>/', WorkerByWorkerIdView.as_view(), name='worker-by-worker-id'),

    # Worker statistics and related data
    path('stats/', worker_stats, name='worker-stats'),
    path('<str:worker_id>/shifts/', worker_shifts, name='worker-shifts'),
    path('<str:worker_id>/violations/', worker_violations, name='worker-violations'),
]
