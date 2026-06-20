"""
Face Recognition Service for worker identification.

Uses InsightFace (SCRFD detector + ArcFace embeddings) for robust, real-world
face recognition. Each worker is enrolled with one or more 512-dimensional
L2-normalized ArcFace embeddings. Recognition is performed with cosine
similarity against an in-memory index built from the database, with a
threshold + margin gate to reduce false matches.

Requires: insightface, onnxruntime (CPU) — optional opencv for blur scoring.
If those packages are not installed the service degrades gracefully and
disables recognition (logs a warning) instead of crashing requests.

Public API is kept backwards compatible with the previous dlib-based service
so existing callers (workers/views.py, detection/views.py, ppe_model.py)
continue to work.
"""
import io
import logging
from typing import Optional, List, Dict, Tuple

import numpy as np
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)

# Identifier stored alongside each worker's embeddings so we can detect and
# ignore stale embeddings produced by a different model/version.
EMBEDDING_MODEL_ID = getattr(settings, 'FACE_EMBEDDING_MODEL', 'arcface_buffalo_l')

# InsightFace model pack. buffalo_l = SCRFD-10GF detector + ArcFace r50 (512-d).
INSIGHTFACE_PACK = getattr(settings, 'INSIGHTFACE_PACK', 'buffalo_l')

# Detector input size (square). Larger = better on small/far faces, slower.
FACE_DET_SIZE = int(getattr(settings, 'FACE_DET_SIZE', 640))

# Cosine-similarity threshold for a positive match (ArcFace embeddings).
# Same-identity pairs typically score well above this; unknowns below.
FACE_COSINE_THRESHOLD = float(getattr(settings, 'FACE_COSINE_THRESHOLD', 0.38))

# Required gap between the best and second-best *different* worker. Prevents
# confidently matching look-alikes when two candidates score similarly.
FACE_MATCH_MARGIN = float(getattr(settings, 'FACE_MATCH_MARGIN', 0.06))

# --- Enrollment quality gate thresholds ---
# Minimum detector confidence for an enrollment face.
ENROLL_MIN_DET_SCORE = float(getattr(settings, 'FACE_ENROLL_MIN_DET_SCORE', 0.6))
# Face box width must be at least this fraction of the image width.
ENROLL_MIN_FACE_RATIO = float(getattr(settings, 'FACE_ENROLL_MIN_FACE_RATIO', 0.12))
# Minimum face box width in pixels.
ENROLL_MIN_FACE_PX = int(getattr(settings, 'FACE_ENROLL_MIN_FACE_PX', 70))
# Laplacian-variance blur floor (only applied when OpenCV is available).
ENROLL_MIN_BLUR_VAR = float(getattr(settings, 'FACE_ENROLL_MIN_BLUR_VAR', 35.0))


class FaceRecognitionService:
    """Service for face recognition operations (ArcFace / InsightFace)."""

    _app = None                # insightface FaceAnalysis instance
    _app_failed = False        # True once we know the model can't load
    _model_loaded = False      # public flag used by health check

    # In-memory recognition index, rebuilt from the database.
    _emb_matrix: Optional[np.ndarray] = None   # (N, 512) L2-normalized
    _emb_worker_ids: List[str] = []            # length N, worker_id per row
    _index_loaded = False

    # ------------------------------------------------------------------ #
    # Model / index loading
    # ------------------------------------------------------------------ #
    @classmethod
    def _get_app(cls):
        """Lazily build the InsightFace FaceAnalysis app (CPU by default)."""
        if cls._app is not None or cls._app_failed:
            return cls._app
        try:
            from insightface.app import FaceAnalysis

            providers = getattr(
                settings, 'INSIGHTFACE_PROVIDERS', ['CPUExecutionProvider']
            )
            app = FaceAnalysis(name=INSIGHTFACE_PACK, providers=providers)
            app.prepare(ctx_id=0, det_size=(FACE_DET_SIZE, FACE_DET_SIZE))
            cls._app = app
            logger.info(
                "InsightFace ready (pack=%s, det_size=%d)",
                INSIGHTFACE_PACK, FACE_DET_SIZE,
            )
        except ImportError:
            cls._app_failed = True
            logger.error(
                "insightface/onnxruntime not installed. Face recognition "
                "disabled. Install with: pip install insightface onnxruntime"
            )
        except Exception as e:  # model download / runtime failure
            cls._app_failed = True
            logger.error("Failed to initialise InsightFace: %s", e)
        return cls._app

    @classmethod
    def load_model(cls):
        """Initialise the model and recognition index (idempotent)."""
        cls._get_app()
        cls.reload_index()
        cls._model_loaded = cls._app is not None

    @classmethod
    def reload_index(cls, force: bool = True):
        """Rebuild the in-memory embedding index from the Worker table."""
        if cls._index_loaded and not force:
            return
        try:
            from workers.models import Worker

            vectors: List[np.ndarray] = []
            worker_ids: List[str] = []
            qs = Worker.objects.filter(is_active=True).exclude(
                face_embeddings__isnull=True
            )
            for worker in qs:
                embeddings = worker.face_embeddings or []
                # Skip workers enrolled with a different embedding model.
                if worker.embedding_model and worker.embedding_model != EMBEDDING_MODEL_ID:
                    continue
                for vec in embeddings:
                    arr = cls._normalize(np.asarray(vec, dtype=np.float32))
                    if arr is not None:
                        vectors.append(arr)
                        worker_ids.append(worker.worker_id)

            if vectors:
                cls._emb_matrix = np.vstack(vectors)
                cls._emb_worker_ids = worker_ids
            else:
                cls._emb_matrix = None
                cls._emb_worker_ids = []

            cls._index_loaded = True
            logger.info(
                "Face index loaded: %d embeddings across %d workers",
                len(worker_ids), len(set(worker_ids)),
            )
        except Exception as e:
            logger.error("Error loading face index: %s", e)
            cls._emb_matrix = None
            cls._emb_worker_ids = []
            cls._index_loaded = True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(vec: np.ndarray) -> Optional[np.ndarray]:
        """L2-normalize a vector; return None if it is degenerate."""
        if vec is None or vec.ndim != 1:
            return None
        norm = np.linalg.norm(vec)
        if norm < 1e-8:
            return None
        return (vec / norm).astype(np.float32)

    @staticmethod
    def _load_rgb(image_bytes_or_path) -> Optional[np.ndarray]:
        """Load an image as an RGB numpy array from bytes or a path."""
        try:
            if isinstance(image_bytes_or_path, (bytes, bytearray)):
                img = Image.open(io.BytesIO(image_bytes_or_path))
            else:
                img = Image.open(image_bytes_or_path)
            return np.asarray(img.convert('RGB'))
        except Exception as e:
            logger.error("Error loading image: %s", e)
            return None

    @classmethod
    def _detect(cls, rgb: np.ndarray) -> list:
        """Run InsightFace detection+embedding. Returns list of Face objects."""
        app = cls._get_app()
        if app is None or rgb is None:
            return []
        try:
            # InsightFace expects BGR.
            bgr = rgb[:, :, ::-1]
            return app.get(bgr)
        except Exception as e:
            logger.error("Face detection failed: %s", e)
            return []

    @staticmethod
    def _largest(faces: list):
        """Return the face with the largest bounding box, or None."""
        if not faces:
            return None
        return max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        )

    # ------------------------------------------------------------------ #
    # Embedding extraction
    # ------------------------------------------------------------------ #
    @classmethod
    def extract_face_encoding(cls, image_path_or_bytes) -> Optional[np.ndarray]:
        """
        Extract a single L2-normalized embedding from the largest face.

        Kept for backwards compatibility; returns None if no face is found.
        """
        rgb = cls._load_rgb(image_path_or_bytes)
        face = cls._largest(cls._detect(rgb))
        if face is None:
            return None
        return cls._normalize(np.asarray(face.embedding, dtype=np.float32))

    @classmethod
    def assess_enrollment_photo(cls, image_bytes: bytes) -> Dict:
        """
        Validate one enrollment photo and return its embedding.

        Returns a dict:
            {ok: bool, reason: str, embedding: list|None, det_score: float}
        """
        rgb = cls._load_rgb(image_bytes)
        if rgb is None:
            return {'ok': False, 'reason': 'Could not read the image.',
                    'embedding': None, 'det_score': 0.0}

        if cls._get_app() is None:
            return {'ok': False, 'reason': 'Face recognition is not available '
                    'on the server.', 'embedding': None, 'det_score': 0.0}

        faces = cls._detect(rgb)
        if not faces:
            return {'ok': False, 'reason': 'No face detected. Use a clear, '
                    'well-lit photo facing the camera.',
                    'embedding': None, 'det_score': 0.0}
        if len(faces) > 1:
            return {'ok': False, 'reason': 'Multiple faces detected. The photo '
                    'must contain exactly one person.',
                    'embedding': None, 'det_score': 0.0}

        face = faces[0]
        det_score = float(getattr(face, 'det_score', 0.0))
        if det_score < ENROLL_MIN_DET_SCORE:
            return {'ok': False, 'reason': 'Face is unclear or low quality.',
                    'embedding': None, 'det_score': det_score}

        img_w = rgb.shape[1]
        face_w = float(face.bbox[2] - face.bbox[0])
        if face_w < ENROLL_MIN_FACE_PX or (face_w / img_w) < ENROLL_MIN_FACE_RATIO:
            return {'ok': False, 'reason': 'Face is too small. Move closer to '
                    'the camera.', 'embedding': None, 'det_score': det_score}

        blur_var = cls._blur_variance(rgb, face.bbox)
        if blur_var is not None and blur_var < ENROLL_MIN_BLUR_VAR:
            return {'ok': False, 'reason': 'Photo is too blurry. Hold steady '
                    'and retake.', 'embedding': None, 'det_score': det_score}

        embedding = cls._normalize(np.asarray(face.embedding, dtype=np.float32))
        if embedding is None:
            return {'ok': False, 'reason': 'Could not compute a face embedding.',
                    'embedding': None, 'det_score': det_score}

        return {'ok': True, 'reason': '', 'embedding': embedding.tolist(),
                'det_score': det_score}

    @staticmethod
    def _blur_variance(rgb: np.ndarray, bbox) -> Optional[float]:
        """Variance of the Laplacian over the face crop (sharpness proxy)."""
        try:
            import cv2
            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            crop = rgb[y1:y2, x1:x2]
            if crop.size == 0:
                return None
            gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return None  # OpenCV missing or crop invalid — skip blur gate

    # ------------------------------------------------------------------ #
    # Recognition / matching
    # ------------------------------------------------------------------ #
    @classmethod
    def _match(cls, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """Match a normalized embedding against the index (cosine + margin)."""
        if cls._emb_matrix is None or embedding is None:
            return None, 0.0

        sims = cls._emb_matrix @ embedding  # cosine (both normalized)

        # Best similarity per worker.
        best_per_worker: Dict[str, float] = {}
        for sim, wid in zip(sims, cls._emb_worker_ids):
            s = float(sim)
            if wid not in best_per_worker or s > best_per_worker[wid]:
                best_per_worker[wid] = s

        ranked = sorted(best_per_worker.items(), key=lambda kv: kv[1], reverse=True)
        top_wid, top_sim = ranked[0]
        second_sim = ranked[1][1] if len(ranked) > 1 else -1.0

        if top_sim >= FACE_COSINE_THRESHOLD and (top_sim - second_sim) >= FACE_MATCH_MARGIN:
            return top_wid, top_sim
        return None, top_sim

    @classmethod
    def recognize_face(cls, face_encoding) -> Optional[str]:
        """Recognize a worker from a (raw or normalized) embedding."""
        if not cls._index_loaded:
            cls.reload_index(force=False)
        embedding = cls._normalize(np.asarray(face_encoding, dtype=np.float32))
        worker_id, _ = cls._match(embedding)
        return worker_id

    @classmethod
    def detect_faces(cls, image_bytes: bytes) -> List[Dict]:
        """Detect all faces; returns pixel locations {top,right,bottom,left}."""
        rgb = cls._load_rgb(image_bytes)
        out = []
        for f in cls._detect(rgb):
            x1, y1, x2, y2 = [int(v) for v in f.bbox]
            out.append({"top": y1, "right": x2, "bottom": y2, "left": x1})
        return out

    @classmethod
    def recognize_faces_in_frame(cls, image_bytes: bytes) -> List[Dict]:
        """
        Detect + recognize every face in a frame in a single detector pass.

        Returns a list of {bbox_px: (x1,y1,x2,y2), worker_id, score}. Use
        ``match_person_to_worker`` to associate these with person boxes.
        """
        if not cls._index_loaded:
            cls.reload_index(force=False)

        rgb = cls._load_rgb(image_bytes)
        results = []
        for f in cls._detect(rgb):
            embedding = cls._normalize(np.asarray(f.embedding, dtype=np.float32))
            worker_id, score = cls._match(embedding)
            x1, y1, x2, y2 = [float(v) for v in f.bbox]
            results.append({
                'bbox_px': (x1, y1, x2, y2),
                'worker_id': worker_id,
                'score': score,
            })
        return results

    @staticmethod
    def match_person_to_worker(person_box_px, frame_faces: List[Dict]) -> Optional[str]:
        """
        Pick the recognized worker for a person box.

        Chooses the largest detected face whose center falls inside the
        person's bounding box. ``person_box_px`` is (x1, y1, x2, y2).
        """
        px1, py1, px2, py2 = person_box_px
        best = None
        best_area = 0.0
        for face in frame_faces:
            if not face.get('worker_id'):
                continue
            fx1, fy1, fx2, fy2 = face['bbox_px']
            cx, cy = (fx1 + fx2) / 2.0, (fy1 + fy2) / 2.0
            if px1 <= cx <= px2 and py1 <= cy <= py2:
                area = (fx2 - fx1) * (fy2 - fy1)
                if area > best_area:
                    best_area = area
                    best = face['worker_id']
        return best

    @classmethod
    def recognize_face_from_bbox(
        cls, image_bytes: bytes, bbox: Dict[str, float]
    ) -> Optional[str]:
        """
        Recognize the worker inside a normalized person bbox {x,y,width,height}.

        Detects faces in the full frame once and associates them with the box.
        Kept for backwards compatibility; prefer ``recognize_faces_in_frame``
        + ``match_person_to_worker`` when handling many persons per frame.
        """
        rgb = cls._load_rgb(image_bytes)
        if rgb is None:
            return None
        h, w = rgb.shape[:2]
        person_box_px = (
            bbox['x'] * w,
            bbox['y'] * h,
            (bbox['x'] + bbox['width']) * w,
            (bbox['y'] + bbox['height']) * h,
        )
        faces = cls.recognize_faces_in_frame(image_bytes)
        return cls.match_person_to_worker(person_box_px, faces)

    # ------------------------------------------------------------------ #
    # Enrollment index management (DB-backed — no joblib model anymore)
    # ------------------------------------------------------------------ #
    @classmethod
    def add_worker_to_model(cls, worker_id: str, face_encoding=None) -> bool:
        """Refresh the index after a worker is enrolled/updated in the DB."""
        cls.reload_index(force=True)
        return True

    @classmethod
    def retrain_from_workers(cls, workers_data=None) -> bool:
        """Rebuild the index from the database (embeddings live in Worker)."""
        cls.reload_index(force=True)
        return True

    @classmethod
    def save_model(cls) -> bool:
        """No-op: embeddings are persisted on the Worker rows."""
        return True

    @classmethod
    def get_worker_count(cls) -> int:
        """Number of distinct workers currently in the recognition index."""
        if not cls._index_loaded:
            cls.reload_index(force=False)
        return len(set(cls._emb_worker_ids))
