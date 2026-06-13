"""
WebSocket consumers for real-time PPE detection.

This consumer accepts binary image frames from the Flutter app,
runs PPE detection, and sends back DetectionResult JSON.
"""
import logging
import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer
import asyncio

from .services import PPEModelService
from .services.notification_service import NotificationService

logger = logging.getLogger('detection')


class DetectionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time PPE detection.

    URL: ws://localhost:8080/ws/detect/

    Protocol:
    1. Client connects
    2. Client sends binary image frames
    3. Server processes each frame and sends DetectionResult JSON
    4. Connection can be closed by either party
    """

    async def connect(self):
        """Handle WebSocket connection."""
        await self.accept()
        self.session_id = f"ws_session_{uuid.uuid4().hex[:12]}"
        self.frame_count = 0
        self.required_ppe = ['hardHat', 'vest']
        self.confidence_threshold = 0.15

        logger.info(f"WebSocket connected: {self.session_id}")

        # Send welcome message
        await self.send_json({
            'type': 'connected',
            'session_id': self.session_id,
            'message': 'WebSocket connection established. Send binary image frames for detection.'
        })

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(f"WebSocket disconnected: {self.session_id}, code: {close_code}")
        raise StopConsumer()

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming WebSocket messages.

        Args:
            text_data: JSON text data (for configuration)
            bytes_data: Binary image data (for detection)
        """
        try:
            # Handle text data (configuration messages)
            if text_data:
                await self.handle_text_message(text_data)

            # Handle binary data (image frames)
            elif bytes_data:
                await self.handle_image_frame(bytes_data)

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })

    async def handle_text_message(self, text_data):
        """Handle JSON text messages for configuration."""
        try:
            data = json.loads(text_data)

            message_type = data.get('type')

            if message_type == 'config':
                # Update detection configuration
                self.required_ppe = data.get('required_ppe', self.required_ppe)
                self.confidence_threshold = data.get('confidence_threshold', self.confidence_threshold)

                await self.send_json({
                    'type': 'config_updated',
                    'required_ppe': self.required_ppe,
                    'confidence_threshold': self.confidence_threshold
                })

            elif message_type == 'ping':
                await self.send_json({'type': 'pong'})

            else:
                await self.send_json({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })

        except json.JSONDecodeError:
            await self.send_json({
                'type': 'error',
                'message': 'Invalid JSON format'
            })

    async def handle_image_frame(self, bytes_data):
        """Handle binary image frames for detection."""
        self.frame_count += 1
        logger.info(f"Frame {self.frame_count} received: {len(bytes_data)} bytes")
        if self.frame_count == 1:
            with open('/tmp/debug_frame.jpg', 'wb') as f:
                f.write(bytes_data)
            logger.info("Saved debug frame to /tmp/debug_frame.jpg")

        try:
            # Run detection in a thread to avoid blocking
            result = await asyncio.to_thread(
                PPEModelService.predict_from_bytes,
                image_bytes=bytes_data,
                conf_threshold=self.confidence_threshold,
                required_ppe=self.required_ppe
            )

            logger.info(f"Frame {self.frame_count} result: detected={result.detected}, compliant={result.compliant}, nonCompliant={result.nonCompliant}")

            # Send detection result
            await self.send_json({
                'type': 'detection',
                'frame_id': result.frameId,
                'frame_number': self.frame_count,
                'detected': result.detected,
                'compliant': result.compliant,
                'non_compliant': result.nonCompliant,
                'detections': result.detections
            })

            # Enforcement (F1): de-duplicate, persist, auto-resolve, notify.
            # Runs for every frame so compliant frames can auto-close violations.
            from channels.db import database_sync_to_async
            from django.core.files.base import ContentFile
            from .services.enforcement import process_detections
            frame_image = ContentFile(bytes_data, name=f"frame_{result.frameId}.jpg")
            await database_sync_to_async(process_detections)(
                result.detections,
                image=frame_image,
                session_id=getattr(self, 'session_id', None),
                required_ppe=self.required_ppe,
            )

        except Exception as e:
            logger.error(f"Error processing image frame: {e}")
            await self.send_json({
                'type': 'error',
                'frame_number': self.frame_count,
                'message': f'Detection failed: {str(e)}'
            })

    async def _send_violation_notification(self, detection):
        """Send violation notification for a non-compliant detection."""
        try:
            worker_id = detection.get('workerId')
            worker_name = detection.get('workerName') or worker_id or 'Unknown'

            # Get missing PPE
            missing_ppe = []
            for ppe in detection.get('ppeStatus', []):
                if ppe.get('status') != 'compliant':
                    missing_ppe.append(ppe.get('type'))

            # Only notify if there's missing PPE
            if missing_ppe:
                await NotificationService.send_violation_notification_async({
                    'worker_id': worker_id,
                    'worker_name': worker_name,
                    'missing_ppe': missing_ppe,
                    'required_ppe': self.required_ppe,
                    'timestamp': None,  # Will use current time
                })

        except Exception as e:
            logger.error(f"Error sending violation notification: {e}")

    async def send_json(self, data):
        """Send JSON data to the client."""
        await self.send(text_data=json.dumps(data))


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.

    URL: ws://localhost:8080/ws/notifications/

    Workers and admins connect here to receive violation notifications.

    Protocol:
    1. Client connects with token in query string
    2. Server authenticates and subscribes to appropriate channels
    3. Client receives notifications in real-time
    4. Connection can be closed by either party
    """

    async def connect(self):
        """Handle WebSocket connection."""
        # Accept the connection
        await self.accept()

        # Get user info from query string (token-based auth)
        query_string = self.scope.get('query_string', b'').decode()
        self.user_id = None
        self.worker_id = None
        self.role = None

        # Parse query parameters
        params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
        self.user_id = params.get('user_id')
        self.role = params.get('role')
        self.worker_id = params.get('worker_id')

        # Subscribe to appropriate channels based on role
        if self.role == 'worker' and self.worker_id:
            # Worker subscribes to their personal channel
            worker_channel = f'worker_{self.worker_id}'
            await self.channel_layer.group_add(
                worker_channel,
                self.channel_name
            )
            logger.info(f"Worker {self.worker_id} connected to notifications")

        elif self.role in ['admin', 'supervisor']:
            # Admins subscribe to admins and monitoring channels
            await self.channel_layer.group_add(
                'admins',
                self.channel_name
            )
            await self.channel_layer.group_add(
                'monitoring',
                self.channel_name
            )
            logger.info(f"Admin {self.user_id} connected to notifications")

        # Send welcome message
        await self.send_json({
            'type': 'connected',
            'message': 'Connected to notification service',
            'role': self.role,
        })

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Unsubscribe from channels
        if self.role == 'worker' and self.worker_id:
            worker_channel = f'worker_{self.worker_id}'
            await self.channel_layer.group_discard(
                worker_channel,
                self.channel_name
            )
        elif self.role in ['admin', 'supervisor']:
            await self.channel_layer.group_discard('admins', self.channel_name)
            await self.channel_layer.group_discard('monitoring', self.channel_name)

        logger.info(f"Notification client disconnected: {close_code}")
        raise StopConsumer()

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming WebSocket messages."""
        try:
            if text_data:
                data = json.loads(text_data)
                message_type = data.get('type')

                if message_type == 'ping':
                    await self.send_json({'type': 'pong'})

                elif message_type == 'mark_read':
                    # Mark notification as read (future: update database)
                    notification_id = data.get('notification_id')
                    logger.info(f"Notification {notification_id} marked as read")

                else:
                    await self.send_json({
                        'type': 'error',
                        'message': f'Unknown message type: {message_type}'
                    })

        except Exception as e:
            logger.error(f"Error processing notification message: {e}")
            await self.send_json({
                'type': 'error',
                'message': str(e)
            })

    async def notification_message(self, event):
        """
        Handle notification messages from channel layer.

        This is called when a notification is sent to a group this consumer is part of.
        """
        # Send the notification data to the client
        await self.send_json(event.get('data', {}))

    async def send_json(self, data):
        """Send JSON data to the client."""
        await self.send(text_data=json.dumps(data))
