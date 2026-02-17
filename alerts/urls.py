"""
URL configuration for Alerts app.
"""
from django.urls import path
from .views import (
    alert_config_list,
    alert_config_create,
    alert_config_detail,
    alert_history,
    alert_stats,
    test_alert,
    recipient_list,
    recipient_detail
)

urlpatterns = [
    # Alert configuration endpoints
    path('config/', alert_config_list, name='alert-config-list'),
    path('config/create/', alert_config_create, name='alert-config-create'),
    path('config/<int:config_id>/', alert_config_detail, name='alert-config-detail'),

    # Alert history and statistics
    path('history/', alert_history, name='alert-history'),
    path('stats/', alert_stats, name='alert-stats'),
    path('test/', test_alert, name='test-alert'),

    # Alert recipients
    path('recipients/', recipient_list, name='recipient-list'),
    path('recipients/<int:recipient_id>/', recipient_detail, name='recipient-detail'),
]
