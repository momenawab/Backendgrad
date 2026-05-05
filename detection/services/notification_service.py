"""
Notification service for PPE violation alerts.

Sends real-time notifications via WebSocket when violations are detected.
Supports severity-based notifications (low vs high).
"""
import logging
import json
import uuid
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

logger = logging.getLogger('detection')


class NotificationService:
    """Service for sending violation notifications."""

    # Channel layer for WebSocket communication
    channel_layer = get_channel_layer()

    @staticmethod
    def calculate_severity(missing_ppe, required_ppe):
        """
        Calculate severity based on missing PPE percentage.

        Args:
            missing_ppe: List of missing PPE types
            required_ppe: List of required PPE types

        Returns:
            'high' if missing 50%+ of required PPE, 'low' otherwise
        """
        required_count = len(required_ppe)
        missing_count = len(missing_ppe)

        if required_count == 0:
            return 'low'

        missing_percentage = (missing_count / required_count) * 100
        return 'high' if missing_percentage >= 50 else 'low'

    @staticmethod
    def send_violation_notification(violation_data):
        """
        Send notification when violation is detected.

        Args:
            violation_data: {
                'worker_id': str,
                'worker_name': str,
                'missing_ppe': list,
                'required_ppe': list,
                'image_url': str,
                'timestamp': datetime,
                'severity': str (optional, auto-calculated if not provided),
            }

        Sends to:
        1. Worker's personal channel (if they have an account)
        2. Admins monitoring channel
        """
        try:
            # Calculate severity if not provided
            if 'severity' not in violation_data:
                violation_data['severity'] = NotificationService.calculate_severity(
                    violation_data['missing_ppe'],
                    violation_data['required_ppe']
                )

            # Create notification payload
            notification_id = f"notif_{uuid.uuid4().hex[:12]}"
            payload = {
                'type': 'violation_notification',
                'notification_id': notification_id,
                'worker_id': violation_data.get('worker_id'),
                'worker_name': violation_data.get('worker_name'),
                'missing_ppe': violation_data.get('missing_ppe', []),
                'required_ppe': violation_data.get('required_ppe', []),
                'severity': violation_data.get('severity', 'low'),
                'image_url': violation_data.get('image_url'),
                'timestamp': (violation_data.get('timestamp') or timezone.now()).isoformat(),
            }

            # Send to worker's personal channel
            worker_id = violation_data.get('worker_id')
            if worker_id:
                worker_channel = f'worker_{worker_id}'
                NotificationService._send_to_channel(worker_channel, payload)

            # Send to admins channel
            admins_channel = 'admins'
            NotificationService._send_to_channel(admins_channel, payload)

            # Send to all monitoring channel
            monitoring_channel = 'monitoring'
            NotificationService._send_to_channel(monitoring_channel, payload)

            logger.info(
                f"Violation notification sent: worker={worker_id}, "
                f"severity={payload['severity']}, missing={len(payload['missing_ppe'])}"
            )

        except Exception as e:
            logger.error(f"Error sending violation notification: {e}")

    @staticmethod
    def _send_to_channel(channel, payload):
        """Send payload to a specific channel (sync context)."""
        try:
            async_to_sync(NotificationService.channel_layer.group_send)(
                channel,
                {
                    'type': 'notification_message',
                    'data': payload,
                }
            )
        except Exception as e:
            logger.error(f"Error sending to channel {channel}: {e}")

    @staticmethod
    async def _send_to_channel_async(channel, payload):
        """Send payload to a specific channel (async context)."""
        try:
            await NotificationService.channel_layer.group_send(
                channel,
                {
                    'type': 'notification_message',
                    'data': payload,
                }
            )
        except Exception as e:
            logger.error(f"Error sending to channel {channel}: {e}")

    @staticmethod
    async def send_violation_notification_async(violation_data):
        """Async version of send_violation_notification for use inside async consumers."""
        try:
            if 'severity' not in violation_data:
                violation_data['severity'] = NotificationService.calculate_severity(
                    violation_data['missing_ppe'],
                    violation_data['required_ppe']
                )

            notification_id = f"notif_{uuid.uuid4().hex[:12]}"
            payload = {
                'type': 'violation_notification',
                'notification_id': notification_id,
                'worker_id': violation_data.get('worker_id'),
                'worker_name': violation_data.get('worker_name'),
                'missing_ppe': violation_data.get('missing_ppe', []),
                'required_ppe': violation_data.get('required_ppe', []),
                'severity': violation_data.get('severity', 'low'),
                'image_url': violation_data.get('image_url'),
                'timestamp': (violation_data.get('timestamp') or timezone.now()).isoformat(),
            }

            worker_id = violation_data.get('worker_id')
            if worker_id:
                await NotificationService._send_to_channel_async(f'worker_{worker_id}', payload)

            await NotificationService._send_to_channel_async('admins', payload)
            await NotificationService._send_to_channel_async('monitoring', payload)

            logger.info(
                f"Violation notification sent: worker={worker_id}, "
                f"severity={payload['severity']}, missing={len(payload['missing_ppe'])}"
            )

        except Exception as e:
            logger.error(f"Error sending violation notification: {e}")

    @staticmethod
    def send_alert_resolved(violation_id, resolved_by):
        """
        Send notification when a violation is resolved.

        Args:
            violation_id: ID of the resolved violation
            resolved_by: Username of who resolved it
        """
        try:
            payload = {
                'type': 'violation_resolved',
                'violation_id': violation_id,
                'resolved_by': resolved_by,
                'timestamp': timezone.now().isoformat(),
            }

            # Send to monitoring channels
            NotificationService._send_to_channel('admins', payload)
            NotificationService._send_to_channel('monitoring', payload)

            logger.info(f"Violation resolved notification sent: {violation_id}")

        except Exception as e:
            logger.error(f"Error sending resolved notification: {e}")

    @staticmethod
    def send_system_alert(message, alert_type='info'):
        """
        Send a system-wide alert.

        Args:
            message: Alert message
            alert_type: 'info', 'warning', 'error'
        """
        try:
            payload = {
                'type': 'system_alert',
                'message': message,
                'alert_type': alert_type,
                'timestamp': timezone.now().isoformat(),
            }

            # Send to all monitoring channels
            NotificationService._send_to_channel('admins', payload)
            NotificationService._send_to_channel('monitoring', payload)

            logger.info(f"System alert sent: {message}")

        except Exception as e:
            logger.error(f"Error sending system alert: {e}")
