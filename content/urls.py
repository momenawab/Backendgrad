"""
URL configuration for the Content app.
"""
from django.urls import path
from .views import HowToStepListView

urlpatterns = [
    path('how-to/', HowToStepListView.as_view(), name='how-to-steps'),
]
