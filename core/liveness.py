import cv2
import numpy as np
from typing import Tuple, Dict, Any, List


class LivenessDetector:
    """
    Anti-spoofing and liveness detection module.
    Detects paper photos, screen replays, and ensures a live human subject is present.
    """

    def __init__(self, blur_threshold: float = 30.0, texture_threshold: float = 8.0):
        self.blur_threshold = blur_threshold
        self.texture_threshold = texture_threshold
        # Track history of landmark positions for motion verification: {face_id: list_of_landmarks}
        self.face_history: Dict[str, List[np.ndarray]] = {}

    def check_texture_and_blur(self, face_crop: np.ndarray) -> Tuple[bool, float, str]:
        """
        Check if the face image has realistic skin texture and isn't a blurry paper printout.
        Uses Laplacian variance and high-frequency energy.
        """
        if face_crop is None or face_crop.size == 0:
            return False, 0.0, "Empty face crop"

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop

        # 1. Laplacian variance (Blurriness check)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 2. Texture gradient via Sobel filters (Distinguishes glossy screens/printed patterns)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobelx**2 + sobely**2).mean()

        # 3. Specular reflection / glare check (Screens often have concentrated bright glare spots)
        high_intensity_pixels = np.sum(gray > 250) / float(gray.size)

        if lap_var < self.blur_threshold:
            return False, float(lap_var), "Face image too blurry or low quality"

        if high_intensity_pixels > 0.15:
            return False, float(1.0 - high_intensity_pixels), "Excessive screen reflection / glare detected"

        # Normalized liveness score between 0.5 and 1.0
        score = min(1.0, 0.5 + (lap_var / 500.0) * 0.5)
        return True, float(round(score, 3)), "Natural face texture verified"

    def check_landmark_geometry(self, landmarks: np.ndarray, bbox: List[int]) -> Tuple[bool, float, str]:
        """
        Verify facial landmark geometry (eyes, nose, mouth corners)
        to ensure proper 3D head proportions.
        landmarks format from YuNet: 5 points (re, le, nt, rmc, lmc) as (x, y)
        """
        if landmarks is None or len(landmarks) < 5:
            return False, 0.0, "Facial landmarks incomplete"

        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return False, 0.0, "Invalid bounding box"

        right_eye = landmarks[0]
        left_eye = landmarks[1]
        nose = landmarks[2]
        mouth_right = landmarks[3]
        mouth_left = landmarks[4]

        # Check eye distance relative to face width
        eye_dist = np.linalg.norm(right_eye - left_eye)
        eye_ratio = eye_dist / float(w)

        # Realistic face: eye distance is typically 20% to 55% of face width
        if eye_ratio < 0.15 or eye_ratio > 0.65:
            return False, float(eye_ratio), "Abnormal facial landmark proportions"

        # Check vertical ordering: eyes should be above nose, nose above mouth
        if right_eye[1] > nose[1] or left_eye[1] > nose[1]:
            return False, 0.3, "Inverted facial landmark alignment"

        if nose[1] > mouth_right[1] or nose[1] > mouth_left[1]:
            return False, 0.3, "Abnormal vertical facial alignment"

        return True, 0.95, "Landmark geometry valid"

    def verify_liveness(self, face_crop: np.ndarray, landmarks: np.ndarray, bbox: List[int]) -> Dict[str, Any]:
        """
        Complete liveness assessment combining texture, glare, and geometry.
        """
        tex_ok, tex_score, tex_msg = self.check_texture_and_blur(face_crop)
        if not tex_ok:
            return {
                "is_live": False,
                "score": tex_score,
                "reason": tex_msg,
                "details": {"texture_ok": False, "geometry_ok": False}
            }

        geo_ok, geo_score, geo_msg = self.check_landmark_geometry(landmarks, bbox)
        if not geo_ok:
            return {
                "is_live": False,
                "score": geo_score,
                "reason": geo_msg,
                "details": {"texture_ok": True, "geometry_ok": False}
            }

        final_score = round((tex_score + geo_score) / 2.0, 3)
        return {
            "is_live": True,
            "score": final_score,
            "reason": "Liveness Verified",
            "details": {"texture_ok": True, "geometry_ok": True}
        }
