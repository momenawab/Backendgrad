from django.urls import path
from .views import IncidentListCreateView, IncidentDetailView

urlpatterns = [
    path('', IncidentListCreateView.as_view(), name='incident-list'),
    path('<int:id>/', IncidentDetailView.as_view(), name='incident-detail'),
]
