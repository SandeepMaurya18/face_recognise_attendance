import os
import sys
import unittest
import numpy as np
import cv2
from datetime import datetime

from database.db import init_db, get_db_connection
from database.models import (
    create_user, get_all_users, get_user_by_id, delete_user,
    log_attendance, get_attendance_logs, get_dashboard_metrics
)
from database.export_utils import export_to_csv, export_to_excel
from core.face_engine import FaceEngine
from core.liveness import LivenessDetector
from core.attendance_service import AttendanceService


class TestAegisFaceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.engine = FaceEngine()
        cls.service = AttendanceService()
        cls.liveness = LivenessDetector()

    def test_01_database_users(self):
        """Test User creation, retrieval, and deletion in SQLite."""
        test_uid = "TEST_EMP_999"
        # Dummy 128D embedding
        dummy_emb = np.random.randn(128).astype(np.float32)
        dummy_emb /= np.linalg.norm(dummy_emb)

        user = create_user(
            user_id=test_uid,
            name="Test User 999",
            department="QA Testing",
            role="Automated Tester",
            email="qa@test.local",
            phone="1234567890",
            photo_path=None,
            embedding=dummy_emb
        )
        self.assertIsNotNone(user)
        self.assertEqual(user["user_id"], test_uid)

        fetched = get_user_by_id(test_uid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "Test User 999")

        # Cleanup
        deleted = delete_user(test_uid)
        self.assertTrue(deleted)
        self.assertIsNone(get_user_by_id(test_uid))

    def test_02_face_engine_models(self):
        """Test YuNet detector and SFace recognizer initialization."""
        self.assertIsNotNone(self.engine.detector)
        self.assertIsNotNone(self.engine.recognizer)
        self.assertGreater(len(self.engine.known_users), 0)

        # Create dummy image and test detection pipeline
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        faces = self.engine.detect_faces(dummy_frame)
        self.assertIsInstance(faces, list)

    def test_03_vector_matching(self):
        """Test normalized cosine similarity matching."""
        users = self.engine.known_users
        self.assertGreater(len(users), 0)
        first_user = users[0]

        # Target embedding matches perfectly
        first_emb = self.engine.known_embeddings[0]
        matched_user, score = self.engine.match_feature(first_emb, threshold=0.45)
        self.assertIsNotNone(matched_user)
        self.assertEqual(matched_user["user_id"], first_user["user_id"])
        self.assertAlmostEqual(score, 1.0, places=3)

    def test_04_liveness_detection(self):
        """Test liveness heuristic checks on blur and screen glare."""
        # Sharp synthetic image
        sharp_crop = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        ok, score, msg = self.liveness.check_texture_and_blur(sharp_crop)
        self.assertTrue(ok)
        self.assertGreater(score, 0.5)

        # Extremely blurry flat image
        flat_crop = np.full((112, 112, 3), 128, dtype=np.uint8)
        ok, score, msg = self.liveness.check_texture_and_blur(flat_crop)
        self.assertFalse(ok)
        self.assertIn("blurry", msg.lower())

    def test_05_attendance_service_rules(self):
        """Test Check-In, Check-Out, and Cooldown logic."""
        test_user = {
            "id": 9999,
            "user_id": "UNIT_TEST_USER",
            "name": "Unit Test User",
            "department": "Engineering"
        }

        # First Punch
        punch1 = self.service.record_punch(test_user, confidence=0.97)
        self.assertTrue(punch1["success"])
        self.assertIn(punch1["action"], ["CHECK_IN", "CHECK_OUT"])

        # Immediate Second Punch should trigger cooldown
        punch2 = self.service.record_punch(test_user, confidence=0.97)
        self.assertFalse(punch2["success"])
        self.assertEqual(punch2["action"], "COOLDOWN_ACTIVE")

    def test_06_manual_attendance_time_controls_status(self):
        settings = {
            "work_start_time": "09:00",
            "work_end_time": "17:00",
            "grace_minutes": "15",
            "manual_attendance_time": "09:30"
        }
        manual_time = self.service.get_attendance_time(settings)

        self.assertEqual(manual_time.strftime("%H:%M"), "09:30")
        self.assertEqual(self.service.calculate_status("CHECK_IN", settings, manual_time), "LATE")
        self.assertEqual(
            self.service.calculate_status("CHECK_IN", settings, manual_time.replace(hour=9, minute=10)),
            "ON_TIME"
        )

    def test_06_reporting_exports(self):
        """Test CSV and Excel export file streams."""
        csv_buf = export_to_csv()
        self.assertGreater(len(csv_buf.getvalue()), 100)

        excel_buf = export_to_excel()
        self.assertGreater(len(excel_buf.getvalue()), 1000)

    def test_07_analytics_kpi_aggregation(self):
        """Test dashboard metrics calculation."""
        metrics = get_dashboard_metrics()
        self.assertIn("total_users", metrics)
        self.assertIn("present_today", metrics)
        self.assertIn("attendance_rate", metrics)
        self.assertIn("department_breakdown", metrics)
        self.assertIn("recent_trend", metrics)


if __name__ == "__main__":
    unittest.main()
