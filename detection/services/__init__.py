"""
Detection services package.
"""
from .ppe_model import PPEModelService
from .face_recognition import FaceRecognitionService
from .notification_service import NotificationService

__all__ = ['PPEModelService', 'FaceRecognitionService', 'NotificationService']
