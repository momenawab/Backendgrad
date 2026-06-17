"""
PPE Model Service - YOLOv11 wrapper for PPE detection.

This service loads the YOLO model and provides methods for PPE detection
on images, returning results in the format expected by the Flutter app.
"""
import os
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict

from PIL import Image
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


# PPE Class mappings from model to Flutter app types
PPE_CLASS_MAP = {
    0: 'gloves',        # Gloves
    1: 'hardHat',       # Helmet
    2: 'person',        # Person
    3: 'steelToedBoots',# Shoes
    4: 'vest',          # Vest
}

# Reverse mapping for Flutter types to model classes
FLUTTER_TO_MODEL_MAP = {
    'hardHat': 1,
    'gloves': 0,
    'vest': 4,
    'steelToedBoots': 3,
}

# PPE types that Flutter app expects but are not in the model
MISSING_PPE_TYPES = ['safetyGlasses', 'earProtection']


@dataclass
class BoundingBox:
    """Bounding box coordinates."""
    x: float
    y: float
    width: float
    height: float


@dataclass
class PPEStatus:
    """PPE item status."""
    type: str
    status: str  # 'compliant' or 'nonCompliant'
    lastDetected: str  # ISO8601 timestamp


@dataclass
class PersonDetection:
    """Detection result for a single person."""
    workerId: Optional[str]
    boundingBox: Dict[str, float]
    ppeStatus: List[Dict[str, Any]]
    overallStatus: str  # 'compliant', 'partial', 'nonCompliant'
    confidence: float


@dataclass
class DetectionResult:
    """Complete detection result for a frame."""
    frameId: str
    detected: int
    compliant: int
    nonCompliant: int
    detections: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'frameId': self.frameId,
            'detected': self.detected,
            'compliant': self.compliant,
            'nonCompliant': self.nonCompliant,
            'detections': self.detections
        }


class PPEModelService:
    """
    Singleton service for PPE detection using YOLOv11.

    The model is loaded once at server startup and reused for all detections.
    """

    _instance = None
    _model = None
    _model_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PPEModelService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the model service (load model if not already loaded)."""
        if not self._model_loaded:
            self.load_model()

    @classmethod
    def load_model(cls) -> None:
        """
        Load the YOLO model from disk.

        This should be called once at server startup.
        The model is cached in the class variable for reuse.
        """
        if cls._model_loaded:
            return

        try:
            from ultralytics import YOLO

            model_path = getattr(settings, 'PPE_MODEL_PATH',
                                 '/Users/momen/StudioProjects/Grad Project/graduation_project 2/best (4).pt')

            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at: {model_path}")

            logger.info(f"Loading PPE detection model from: {model_path}")
            cls._model = YOLO(model_path)
            cls._model_loaded = True
            logger.info("PPE detection model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load PPE model: {e}")
            raise

    @classmethod
    def predict(
        cls,
        image,
        conf_threshold: float = None,
        required_ppe: List[str] = None,
        image_bytes: bytes = None
    ) -> DetectionResult:
        """
        Run PPE detection on an image.

        Args:
            image: Image file path, PIL Image, or numpy array
            conf_threshold: Confidence threshold for detections (default from settings)
            required_ppe: List of required PPE types for compliance checking
            image_bytes: Original image bytes for face recognition (optional)

        Returns:
            DetectionResult object with detection data
        """
        if not cls._model_loaded:
            cls.load_model()

        if conf_threshold is None:
            conf_threshold = getattr(settings, 'DETECTION_CONFIDENCE_THRESHOLD', 0.5)

        # Default required PPE if not specified
        if required_ppe is None:
            required_ppe = ['hardHat', 'vest', 'gloves', 'steelToedBoots']

        try:
            # Run inference
            results = cls._model(image, conf=conf_threshold, verbose=False)

            # Parse results (pass image_bytes for face recognition)
            return cls._parse_results(
                results[0],
                required_ppe=required_ppe,
                image_bytes=image_bytes
            )

        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            # Return empty result on error
            return DetectionResult(
                frameId=str(uuid.uuid4()),
                detected=0,
                compliant=0,
                nonCompliant=0,
                detections=[]
            )

    @classmethod
    def _parse_results(
        cls,
        result,
        required_ppe: List[str],
        image_bytes: bytes = None
    ) -> DetectionResult:
        """
        Parse YOLO result into DetectionResult format.

        Args:
            result: YOLO result object
            required_ppe: List of required PPE types
            image_bytes: Original image bytes for face recognition (optional)

        Returns:
            DetectionResult object
        """
        from .face_recognition import FaceRecognitionService
        frame_id = str(uuid.uuid4())

        # Get boxes and classes
        boxes = result.boxes
        img_height, img_width = result.orig_shape  # YOLO orig_shape is (H, W)

        # Group detections by person
        person_indices = [i for i, cls_id in enumerate(boxes.cls) if int(cls_id) == 2]

        # If no person box detected, synthesize one from all PPE boxes
        if not person_indices:
            ppe_indices = [i for i, cls_id in enumerate(boxes.cls) if int(cls_id) != 2]
            if ppe_indices:
                all_boxes = boxes.xyxy[ppe_indices].cpu().numpy()
                synth_x1 = float(all_boxes[:, 0].min())
                synth_y1 = float(all_boxes[:, 1].min())
                synth_x2 = float(all_boxes[:, 2].max())
                synth_y2 = float(all_boxes[:, 3].max())
                # Expand vertically to approximate full body
                height = synth_y2 - synth_y1
                synth_y1 = max(0, synth_y1 - height * 0.3)
                synth_y2 = min(img_height, synth_y2 + height * 0.3)
                synth_box = np.array([synth_x1, synth_y1, synth_x2, synth_y2])

                bbox = BoundingBox(
                    x=float(synth_x1 / img_width),
                    y=float(synth_y1 / img_height),
                    width=float((synth_x2 - synth_x1) / img_width),
                    height=float((synth_y2 - synth_y1) / img_height)
                )
                detected_ppe = cls._find_ppe_for_person(boxes, synth_box, img_width, img_height)
                ppe_status_list = cls._calculate_ppe_status(detected_ppe, required_ppe)
                overall_status = cls._determine_overall_status(ppe_status_list)
                avg_conf = float(np.mean([float(boxes.conf[i]) for i in ppe_indices]))

                worker_id = None
                if image_bytes is not None:
                    try:
                        worker_id = FaceRecognitionService.recognize_face_from_bbox(
                            image_bytes, asdict(bbox)
                        )
                    except Exception as e:
                        logger.debug(f"Face recognition failed for person: {e}")

                person_detection = PersonDetection(
                    workerId=worker_id,
                    boundingBox=asdict(bbox),
                    ppeStatus=ppe_status_list,
                    overallStatus=overall_status,
                    confidence=avg_conf
                )
                compliant_count = 1 if overall_status == 'compliant' else 0
                non_compliant_count = 0 if overall_status == 'compliant' else 1
                return DetectionResult(
                    frameId=frame_id,
                    detected=1,
                    compliant=compliant_count,
                    nonCompliant=non_compliant_count,
                    detections=[asdict(person_detection)]
                )
            # Truly nothing detected
            return DetectionResult(frameId=frame_id, detected=0, compliant=0, nonCompliant=0, detections=[])

        person_detections = []
        compliant_count = 0
        non_compliant_count = 0

        for person_idx in person_indices:
            person_box = boxes.xyxy[person_idx].cpu().numpy()
            person_conf = float(boxes.conf[person_idx])

            # Get person bounding box (normalized to 0-1)
            x1, y1, x2, y2 = person_box
            bbox = BoundingBox(
                x=float(x1 / img_width),
                y=float(y1 / img_height),
                width=float((x2 - x1) / img_width),
                height=float((y2 - y1) / img_height)
            )

            # Find PPE items associated with this person (within person box)
            detected_ppe = cls._find_ppe_for_person(boxes, person_box, img_width, img_height)

            # Calculate compliance
            ppe_status_list = cls._calculate_ppe_status(
                detected_ppe,
                required_ppe
            )

            # Determine overall status
            overall_status = cls._determine_overall_status(ppe_status_list)

            if overall_status == 'compliant':
                compliant_count += 1
            else:
                non_compliant_count += 1

            # Identify the worker via face recognition (best-effort).
            # Requires the original frame bytes; skips silently if unavailable
            # or if no face is matched within the distance threshold.
            worker_id = None
            if image_bytes is not None:
                try:
                    worker_id = FaceRecognitionService.recognize_face_from_bbox(
                        image_bytes, asdict(bbox)
                    )
                except Exception as e:
                    logger.debug(f"Face recognition failed for person: {e}")

            # Create person detection
            person_detection = PersonDetection(
                workerId=worker_id,  # Populated by face recognition if available
                boundingBox=asdict(bbox),
                ppeStatus=ppe_status_list,
                overallStatus=overall_status,
                confidence=person_conf
            )

            person_detections.append(asdict(person_detection))

        return DetectionResult(
            frameId=frame_id,
            detected=len(person_detections),
            compliant=compliant_count,
            nonCompliant=non_compliant_count,
            detections=person_detections
        )

    @classmethod
    def _find_ppe_for_person(
        cls,
        boxes,
        person_box: np.ndarray,
        img_width: int,
        img_height: int
    ) -> Dict[str, Tuple[float, float]]:
        """
        Find PPE items associated with a person.

        Args:
            boxes: YOLO boxes object
            person_box: Person bounding box [x1, y1, x2, y2]
            img_width: Image width
            img_height: Image height

        Returns:
            Dictionary mapping PPE type to (confidence, area)
        """
        detected_ppe = {}
        px1, py1, px2, py2 = person_box
        person_area = (px2 - px1) * (py2 - py1)

        for i, cls in enumerate(boxes.cls):
            cls_id = int(cls)

            # Skip persons
            if cls_id == 2:
                continue

            # Get PPE type
            ppe_type = PPE_CLASS_MAP.get(cls_id)
            if not ppe_type:
                continue

            # Check if PPE is within or overlapping person box
            box = boxes.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = box

            # Calculate intersection over union (IoU) or simple overlap
            intersection = (
                max(0, min(x2, px2) - max(x1, px1)) *
                max(0, min(y2, py2) - max(y1, py1))
            )

            # If significant overlap, associate PPE with person
            if intersection > 0:
                conf = float(boxes.conf[i])
                area = (x2 - x1) * (y2 - y1)

                # Keep the PPE with highest confidence
                if ppe_type not in detected_ppe or conf > detected_ppe[ppe_type][0]:
                    detected_ppe[ppe_type] = (conf, area)

        return detected_ppe

    @classmethod
    def _calculate_ppe_status(
        cls,
        detected_ppe: Dict[str, Tuple[float, float]],
        required_ppe: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Calculate status for each PPE type.

        Args:
            detected_ppe: Dictionary of detected PPE with confidence
            required_ppe: List of required PPE types

        Returns:
            List of PPE status dictionaries
        """
        ppe_status_list = []
        now = datetime.utcnow().isoformat() + 'Z'

        for ppe_type in required_ppe:
            # Check if PPE type is supported by model
            if ppe_type in MISSING_PPE_TYPES:
                # For unsupported types, mark as not detected
                # In production, these could be detected by additional models
                ppe_status_list.append({
                    'type': ppe_type,
                    'status': 'nonCompliant',
                    'lastDetected': None
                })
            elif ppe_type in detected_ppe:
                conf, _ = detected_ppe[ppe_type]
                ppe_status_list.append({
                    'type': ppe_type,
                    'status': 'compliant',
                    'lastDetected': now
                })
            else:
                ppe_status_list.append({
                    'type': ppe_type,
                    'status': 'nonCompliant',
                    'lastDetected': None
                })

        return ppe_status_list

    @classmethod
    def _determine_overall_status(cls, ppe_status_list: List[Dict[str, Any]]) -> str:
        """
        Determine overall compliance status.

        Args:
            ppe_status_list: List of PPE status dictionaries

        Returns:
            'compliant', 'partial', or 'nonCompliant'
        """
        if not ppe_status_list:
            return 'nonCompliant'

        compliant_count = sum(1 for s in ppe_status_list if s['status'] == 'compliant')
        total_count = len(ppe_status_list)

        if compliant_count == total_count:
            return 'compliant'
        elif compliant_count > 0:
            return 'partial'
        else:
            return 'nonCompliant'

    @classmethod
    def predict_from_bytes(
        cls,
        image_bytes: bytes,
        conf_threshold: float = None,
        required_ppe: List[str] = None
    ) -> DetectionResult:
        """
        Run PPE detection on image bytes.

        Args:
            image_bytes: Raw image bytes
            conf_threshold: Confidence threshold for detections
            required_ppe: List of required PPE types

        Returns:
            DetectionResult object
        """
        try:
            # Load image from bytes
            import io
            image = Image.open(io.BytesIO(image_bytes))
            image = image.convert('RGB')

            # Pass image_bytes for face recognition
            return cls.predict(image, conf_threshold, required_ppe, image_bytes=image_bytes)

        except Exception as e:
            logger.error(f"Error processing image bytes: {e}")
            return DetectionResult(
                frameId=str(uuid.uuid4()),
                detected=0,
                compliant=0,
                nonCompliant=0,
                detections=[]
            )


# Preload model on import
try:
    PPEModelService.load_model()
except Exception as e:
    logger.warning(f"Could not preload PPE model: {e}")
