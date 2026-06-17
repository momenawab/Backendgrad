"""
Face Recognition Service for worker identification.

Uses the face_recognition library and extends the existing
face_recognition_model.joblib trained on celebrities.

Requires: Python 3.7-3.11, dlib, face-recognition
"""
import os
import logging
import numpy as np
import joblib
from PIL import Image
from typing import Optional, List, Dict, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)

# Path to the existing model (trained on celebrities)
# The model is in "graduation_project 2" folder
FACE_MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    '../graduation_project 2/face_recognition_model.joblib'
)

# Path for our worker-specific model
WORKER_MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    'models/face_recognition_workers.joblib'
)

WORKER_MAPPING_PATH = os.path.join(
    settings.BASE_DIR,
    'models/face_recognition_workers_mapping.pkl'
)

# Distance threshold for recognition (from notebook)
FACE_DISTANCE_THRESHOLD = 0.6


class FaceRecognitionService:
    """Service for face recognition operations."""

    _knn_clf = None
    _worker_id_map = []  # Maps KNN class indices to worker_ids
    _model_loaded = False
    _original_class_count = 0  # Number of classes in the original celebrity model

    @classmethod
    def load_model(cls):
        """Load the KNN classifier for face recognition."""
        if cls._model_loaded:
            return

        try:
            # Try to load the worker-specific model first
            if os.path.exists(WORKER_MODEL_PATH):
                cls._knn_clf = joblib.load(WORKER_MODEL_PATH)
                cls._load_worker_mapping()
                logger.info("Worker face recognition model loaded")
            elif os.path.exists(FACE_MODEL_PATH):
                # Load the original celebrity-trained model
                cls._knn_clf = joblib.load(FACE_MODEL_PATH)
                logger.info("Base face recognition model loaded (celebrity-trained)")
            else:
                logger.warning("No face recognition model found, face recognition disabled")
                cls._knn_clf = None

            cls._model_loaded = True

        except Exception as e:
            logger.error(f"Failed to load face model: {e}")
            cls._knn_clf = None
            cls._model_loaded = True

    @classmethod
    def _load_worker_mapping(cls):
        """Load the worker_id mapping from disk."""
        try:
            if os.path.exists(WORKER_MAPPING_PATH):
                cls._worker_id_map = joblib.load(WORKER_MAPPING_PATH)
                logger.info(f"Loaded {len(cls._worker_id_map)} worker mappings")
            else:
                cls._worker_id_map = []
        except Exception as e:
            logger.error(f"Error loading worker mapping: {e}")
            cls._worker_id_map = []

    @classmethod
    def extract_face_encoding(cls, image_path_or_bytes) -> Optional[np.ndarray]:
        """
        Extract 128-dimensional face encoding from an image.

        Args:
            image_path_or_bytes: File path string or image bytes

        Returns:
            128-dim encoding array or None if no face detected
        """
        try:
            import face_recognition

            # Load image
            if isinstance(image_path_or_bytes, bytes):
                import io
                image = face_recognition.load_image_file(io.BytesIO(image_path_or_bytes))
            else:
                image = face_recognition.load_image_file(image_path_or_bytes)

            # Extract face encodings (get first face only)
            encodings = face_recognition.face_encodings(image)

            if len(encodings) > 0:
                return encodings[0]

            return None

        except ImportError:
            logger.error("face_recognition library not installed. Install with: pip install face-recognition")
            return None
        except SystemExit as e:
            # face_recognition calls quit()/sys.exit() at import time when the
            # face_recognition_models weights package is missing. SystemExit is a
            # BaseException, so catch it explicitly to avoid killing the request.
            logger.error(
                "face_recognition_models not installed. Install with: "
                "pip install git+https://github.com/ageitgey/face_recognition_models"
            )
            return None
        except Exception as e:
            logger.error(f"Error extracting face encoding: {e}")
            return None

    @classmethod
    def detect_faces(cls, image_bytes: bytes) -> List[Dict]:
        """
        Detect all faces in an image.

        Args:
            image_bytes: Image as bytes

        Returns:
            List of face locations (top, right, bottom, left)
        """
        try:
            import face_recognition
            import io

            image = face_recognition.load_image_file(io.BytesIO(image_bytes))
            face_locations = face_recognition.face_locations(image, model="hog")

            return [
                {"top": t, "right": r, "bottom": b, "left": l}
                for t, r, b, l in face_locations
            ]
        except SystemExit:
            logger.error(
                "face_recognition_models not installed. Install with: "
                "pip install git+https://github.com/ageitgey/face_recognition_models"
            )
            return []
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []

    @classmethod
    def recognize_face(cls, face_encoding: np.ndarray) -> Optional[str]:
        """
        Recognize a face from its encoding.

        Args:
            face_encoding: 128-dimensional face encoding

        Returns:
            worker_id if recognized, None otherwise
        """
        if not cls._model_loaded:
            cls.load_model()

        if cls._knn_clf is None:
            return None

        try:
            # Find closest matches
            distances, indices = cls._knn_clf.kneighbors(
                [face_encoding],
                n_neighbors=1
            )

            distance = distances[0][0]
            class_index = int(indices[0][0])

            # Check if within threshold
            if distance < FACE_DISTANCE_THRESHOLD:
                # Map class index to worker_id
                if class_index < len(cls._worker_id_map):
                    return cls._worker_id_map[class_index]

            return None

        except Exception as e:
            logger.error(f"Error recognizing face: {e}")
            return None

    @classmethod
    def recognize_face_from_bbox(
        cls,
        image_bytes: bytes,
        bbox: Dict[str, float]
    ) -> Optional[str]:
        """
        Recognize a face from a bounding box in an image.

        Args:
            image_bytes: Original image bytes
            bbox: Normalized bounding box {x, y, width, height} (0-1)

        Returns:
            worker_id if recognized, None otherwise
        """
        try:
            import io

            # Load image and get dimensions
            image = Image.open(io.BytesIO(image_bytes))
            img_width, img_height = image.size

            # Convert normalized bbox to pixel coordinates
            x1 = int(bbox['x'] * img_width)
            y1 = int(bbox['y'] * img_height)
            x2 = int((bbox['x'] + bbox['width']) * img_width)
            y2 = int((bbox['y'] + bbox['height']) * img_height)

            # Expand bbox to include head/face area
            # Face is typically in upper portion of person bbox
            head_height = int((y2 - y1) * 0.5)  # Top 50%
            face_y1 = max(0, y1)
            face_y2 = min(img_height, y1 + head_height)

            # Add some padding
            padding = int((x2 - x1) * 0.15)
            face_x1 = max(0, x1 - padding)
            face_x2 = min(img_width, x2 + padding)

            # Validate crop region is non-empty before cropping
            if face_x2 <= face_x1 or face_y2 <= face_y1:
                return None

            # Crop face region
            face_region = image.crop((face_x1, face_y1, face_x2, face_y2))

            # Extract encoding directly from the PIL Image/numpy array
            try:
                import face_recognition
                # Convert PIL to numpy array (RGB format)
                face_array = np.array(face_region)

                # face_recognition needs RGB format, PIL gives RGB
                encodings = face_recognition.face_encodings(face_array)
                if len(encodings) > 0:
                    return cls.recognize_face(encodings[0])
            except SystemExit:
                logger.error(
                    "face_recognition_models not installed. Install with: "
                    "pip install git+https://github.com/ageitgey/face_recognition_models"
                )
            except Exception as e:
                logger.debug(f"Face encoding failed from bbox: {e}")

            return None

        except Exception as e:
            logger.error(f"Error recognizing face from bbox: {e}")
            return None

    @classmethod
    def add_worker_to_model(cls, worker_id: str, face_encoding: np.ndarray) -> bool:
        """
        Add a new worker to the face recognition model.

        This creates/extends a worker-only KNN classifier.

        Args:
            worker_id: Unique worker identifier
            face_encoding: 128-dimensional face encoding

        Returns:
            True if successful, False otherwise
        """
        try:
            # Always build a worker-only model (don't use celebrity model)
            # Load existing worker data if any
            cls._load_worker_mapping()

            # Build training data from worker map and new encoding
            X_list = []
            y_list = []

            # Add existing workers
            for existing_worker_id in cls._worker_id_map:
                try:
                    from workers.models import Worker
                    worker = Worker.objects.get(worker_id=existing_worker_id)
                    if worker.face_encoding:
                        X_list.append(np.array(worker.face_encoding))
                        y_list.append(len(X_list) - 1)  # Index in X_list
                except Worker.DoesNotExist:
                    continue

            # Add new worker
            X_list.append(face_encoding)
            y_list.append(len(X_list) - 1)
            cls._worker_id_map.append(worker_id)

            # Create new KNN with all workers
            if X_list:
                X = np.array(X_list)
                y = np.array(y_list)

                from sklearn.neighbors import KNeighborsClassifier
                cls._knn_clf = KNeighborsClassifier(
                    n_neighbors=1,
                    weights='distance',
                    metric='euclidean'
                )
                cls._knn_clf.fit(X, y)

                # Save model
                return cls.save_model()

            return False

        except Exception as e:
            logger.error(f"Error adding worker to model: {e}")
            return False

    @classmethod
    def save_model(cls) -> bool:
        """Save the current model to disk."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(WORKER_MODEL_PATH), exist_ok=True)

            # Save model
            joblib.dump(cls._knn_clf, WORKER_MODEL_PATH)

            # Save worker_id mapping separately
            joblib.dump(cls._worker_id_map, WORKER_MAPPING_PATH)

            logger.info(f"Model saved to {WORKER_MODEL_PATH}")
            return True

        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    @classmethod
    def retrain_from_workers(cls, workers_data: List[Dict]) -> bool:
        """
        Completely retrain the model with existing workers.

        Args:
            workers_data: List of {worker_id, face_encoding} dicts

        Returns:
            True if successful
        """
        try:
            if not workers_data:
                logger.warning("No workers data provided for retraining")
                return False

            # Build training data
            X = np.array([w['face_encoding'] for w in workers_data])
            y = np.array([i for i in range(len(workers_data))])

            # Update worker mapping
            cls._worker_id_map = [w['worker_id'] for w in workers_data]

            # Train new KNN classifier
            from sklearn.neighbors import KNeighborsClassifier
            cls._knn_clf = KNeighborsClassifier(
                n_neighbors=1,
                weights='distance',
                metric='euclidean'
            )
            cls._knn_clf.fit(X, y)

            cls._model_loaded = True

            # Save model
            return cls.save_model()

        except Exception as e:
            logger.error(f"Error retraining model: {e}")
            return False

    @classmethod
    def get_worker_count(cls) -> int:
        """Return the number of workers in the model."""
        cls.load_model()
        return len(cls._worker_id_map)


# Face recognition preload disabled — enable when face_recognition_models is installed
