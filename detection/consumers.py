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
        self.required_ppe = ['hardHat', 'vest', 'gloves', 'steelToedBoots']
        self.confidence_threshold = 0.5

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

        try:
            # Run detection in a thread to avoid blocking
            result = await asyncio.to_thread(
                PPEModelService.predict_from_bytes,
                image_bytes=bytes_data,
                conf_threshold=self.confidence_threshold,
                required_ppe=self.required_ppe
            )

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

        except Exception as e:
            logger.error(f"Error processing image frame: {e}")
            await self.send_json({
                'type': 'error',
                'frame_number': self.frame_count,
                'message': f'Detection failed: {str(e)}'
            })

    async def send_json(self, data):
        """Send JSON data to the client."""
        await self.send(text_data=json.dumps(data))
