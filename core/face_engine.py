import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np

from database.models import get_all_users_with_embeddings, get_settings
from core.liveness import LivenessDetector

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


class FaceEngine:
    """
    AI/ML Face Engine coordinating YuNet detection, SFace 128D recognition,
    liveness verification, and vectorized biometric matching.
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FaceEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        with self._lock:
            if hasattr(self, "_initialized") and self._initialized:
                return

            if not YUNET_PATH.exists():
                raise FileNotFoundError(f"YuNet model not found at {YUNET_PATH}")
            if not SFACE_PATH.exists():
                raise FileNotFoundError(f"SFace model not found at {SFACE_PATH}")

            # Initialize OpenCV DNN models
            self.detector = cv2.FaceDetectorYN.create(str(YUNET_PATH), "", (320, 320), 0.6, 0.3, 5000)
            self.recognizer = cv2.FaceRecognizerSF.create(str(SFACE_PATH), "")
            self.liveness_detector = LivenessDetector()

            self.current_input_size = (320, 320)

            # In-memory vector database
            self.known_users: List[Dict[str, Any]] = []
            self.known_embeddings: Optional[np.ndarray] = None  # Matrix of shape (N, 128)

            self.reload_known_faces()
            self._initialized = True

    def reload_known_faces(self):
        """Reload enrolled users and normalize their embeddings in memory."""
        users = get_all_users_with_embeddings()
        embeddings_list = []
        user_metadata = []

        for u in users:
            emb = u.get("embedding")
            if emb is not None and len(emb) == 128:
                norm = np.linalg.norm(emb)
                if norm > 1e-6:
                    normalized_emb = (emb / norm).astype(np.float32)
                    embeddings_list.append(normalized_emb)
                    user_metadata.append({
                        "id": u["id"],
                        "user_id": u["user_id"],
                        "name": u["name"],
                        "department": u["department"],
                        "role": u.get("role", "Staff"),
                        "photo_path": u.get("photo_path")
                    })

        with self._lock:
            self.known_users = user_metadata
            if embeddings_list:
                self.known_embeddings = np.vstack(embeddings_list)
            else:
                self.known_embeddings = None

    def detect_faces(self, image: np.ndarray, score_threshold: float = 0.55) -> List[np.ndarray]:
        """
        Run YuNet face detection on an input image.
        Returns array of detected faces or empty list.
        """
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        if self.current_input_size != (w, h):
            self.detector.setInputSize((w, h))
            self.current_input_size = (w, h)

        self.detector.setScoreThreshold(score_threshold)
        _, faces = self.detector.detect(image)

        if faces is None or len(faces) == 0:
            return []

        return faces

    def extract_face_feature(self, image: np.ndarray, face_row: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Align and crop face using 5 landmarks, then extract 128D normalized feature embedding.
        """
        aligned_face = self.recognizer.alignCrop(image, face_row)
        feat = self.recognizer.feature(aligned_face).flatten()
        norm = np.linalg.norm(feat)
        normalized_feat = feat / norm if norm > 1e-6 else feat
        return aligned_face, normalized_feat.astype(np.float32)

    def match_feature(self, query_emb: np.ndarray, threshold: float = 0.45) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Perform vectorized cosine similarity search against enrolled users.
        Returns (matched_user_dict, similarity_score).
        """
        if self.known_embeddings is None or len(self.known_users) == 0:
            return None, 0.0

        # Cosine similarity is dot product of normalized vectors
        scores = np.dot(self.known_embeddings, query_emb)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score >= threshold:
            return self.known_users[best_idx], best_score
        else:
            return None, best_score

    def process_frame(
        self,
        frame: np.ndarray,
        threshold: Optional[float] = None,
        enable_liveness: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Full inference pipeline for a video frame:
        1. Multi-face YuNet detection
        2. Alignment & SFace 128D embedding extraction
        3. Liveness / Anti-spoofing verification
        4. Vector cosine similarity matching
        """
        if threshold is None:
            settings = get_settings()
            threshold = float(settings.get("similarity_threshold", 0.45))

        faces = self.detect_faces(frame)
        results = []

        h, w = frame.shape[:2]

        for face in faces:
            # YuNet output: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rmc, y_rmc, x_lmc, y_lmc, score]
            x, y, fw, fh = map(int, face[0:4])
            det_score = float(face[14])

            # Keep bounding box within frame bounds
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w, x + fw)
            y2 = min(h, y + fh)

            if x2 <= x1 or y2 <= y1:
                continue

            face_crop = frame[y1:y2, x1:x2]

            # Landmarks: 5 points (re, le, nt, rmc, lmc)
            landmarks = face[4:14].reshape((5, 2))

            # Liveness Verification
            liveness_info = {"is_live": True, "score": 1.0, "reason": "Liveness check disabled"}
            if enable_liveness:
                liveness_info = self.liveness_detector.verify_liveness(face_crop, landmarks, [x1, y1, x2 - x1, y2 - y1])

            # Extract biometric feature
            aligned_face, feat = self.extract_face_feature(frame, face)

            # Match against database
            matched_user, similarity = self.match_feature(feat, threshold=threshold)

            # Determine match status
            if not liveness_info["is_live"]:
                status = "SPOOF_REJECTED"
            elif matched_user is not None:
                status = "IDENTIFIED"
            else:
                status = "UNKNOWN"

            results.append({
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "detection_score": round(det_score, 3),
                "landmarks": landmarks.tolist(),
                "user": matched_user,
                "similarity": round(similarity, 4),
                "liveness": liveness_info,
                "status": status,
                "aligned_face": aligned_face
            })

        return results
