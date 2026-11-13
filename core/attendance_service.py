import os
import time
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np

from database.models import (
    log_attendance,
    get_user_today_punches,
    get_settings
)
from database.db import SNAPSHOTS_DIR


class AttendanceService:
    """
    Manages automated attendance processing, duplicate cooldown prevention,
    shift scheduling (On-Time / Late / Early Departure), and audit snapshots.
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AttendanceService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Keep track of last punch timestamp per user to enforce cooldown
        self.last_punch_time: Dict[str, float] = {}

    def is_in_cooldown(self, user_id: str, cooldown_seconds: float) -> Tuple[bool, float]:
        """
        Check if user is within the cooldown period.
        Returns (is_cooldown, remaining_seconds).
        """
        now = time.time()
        last_time = self.last_punch_time.get(user_id)
        if last_time is None:
            return False, 0.0

        elapsed = now - last_time
        if elapsed < cooldown_seconds:
            return True, round(cooldown_seconds - elapsed, 1)

        return False, 0.0

    def calculate_status(
        self,
        punch_type: str,
        settings: Dict[str, str],
        current_time: Optional[datetime] = None
    ) -> str:
        """
        Compute attendance status (ON_TIME, LATE, EARLY_DEPARTURE, NORMAL)
        based on configured working hours and grace period.
        """
        now = current_time or datetime.now()
        current_time_str = now.strftime("%H:%M")

        work_start = settings.get("work_start_time", "09:00")
        work_end = settings.get("work_end_time", "17:00")
        grace_mins = int(settings.get("grace_minutes", "15"))

        # Convert strings to minutes since midnight for easy comparison
        def to_minutes(time_str: str) -> int:
            parts = time_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        current_mins = to_minutes(current_time_str)
        start_mins = to_minutes(work_start)
        end_mins = to_minutes(work_end)

        if punch_type == "CHECK_IN":
            if current_mins <= (start_mins + grace_mins):
                return "ON_TIME"
            else:
                return "LATE"
        else:  # CHECK_OUT
            if current_mins < end_mins:
                return "EARLY_DEPARTURE"
            else:
                return "NORMAL"

    def get_attendance_time(self, settings: Dict[str, str]) -> datetime:
        """Return the real time or the configured manual attendance time."""
        manual_time = settings.get("manual_attendance_time", "").strip()
        if manual_time:
            try:
                parsed_time = datetime.strptime(manual_time, "%H:%M").time()
                return datetime.combine(datetime.now().date(), parsed_time)
            except ValueError:
                pass
        return datetime.now()

    def record_punch(
        self,
        user: Dict[str, Any],
        confidence: float,
        liveness_score: float = 1.0,
        face_snapshot: Optional[np.ndarray] = None,
        force_punch_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a recognition event and records an attendance punch if cooldown has passed.
        """
        user_id = user["user_id"]
        settings = get_settings()
        cooldown_secs = float(settings.get("cooldown_seconds", "60"))

        with self._lock:
            # 1. Cooldown check
            in_cooldown, remaining = self.is_in_cooldown(user_id, cooldown_secs)
            if in_cooldown:
                return {
                    "success": False,
                    "action": "COOLDOWN_ACTIVE",
                    "message": f"Welcome back, {user['name']}. Already logged recently.",
                    "cooldown_remaining": remaining,
                    "user": user
                }

            # 2. Determine Punch Type (CHECK_IN vs CHECK_OUT)
            today_punches = get_user_today_punches(user_id)
            if force_punch_type:
                punch_type = force_punch_type
                if punch_type not in ("CHECK_IN", "CHECK_OUT"):
                    return {
                        "success": False,
                        "action": "INVALID_PUNCH_TYPE",
                        "message": "Choose Check In or Check Out."
                    }

                last_punch = today_punches[-1] if today_punches else None
                if punch_type == "CHECK_IN" and last_punch and last_punch["punch_type"] == "CHECK_IN":
                    return {
                        "success": False,
                        "action": "ALREADY_CHECKED_IN",
                        "message": f"{user['name']} is already checked in. Check out before checking in again.",
                        "user": user
                    }
                if punch_type == "CHECK_OUT" and (not last_punch or last_punch["punch_type"] != "CHECK_IN"):
                    return {
                        "success": False,
                        "action": "NOT_CHECKED_IN",
                        "message": f"{user['name']} is not checked in. Check in before checking out.",
                        "user": user
                    }
            elif not today_punches:
                punch_type = "CHECK_IN"
            else:
                last_punch = today_punches[-1]
                punch_type = "CHECK_OUT" if last_punch["punch_type"] == "CHECK_IN" else "CHECK_IN"

            # 3. Calculate Status (ON_TIME, LATE, etc.)
            attendance_time = self.get_attendance_time(settings)
            status = self.calculate_status(punch_type, settings, attendance_time)

            # 4. Save Audit Snapshot image
            snapshot_path = None
            if face_snapshot is not None and face_snapshot.size > 0:
                timestamp_str = attendance_time.strftime("%Y%m%d_%H%M%S")
                filename = f"snap_{user_id}_{timestamp_str}_{punch_type}.jpg"
                full_path = SNAPSHOTS_DIR / filename
                cv2.imwrite(str(full_path), face_snapshot)
                snapshot_path = f"/data/snapshots/{filename}"

            # 5. Insert Record into DB
            record = log_attendance(
                user_id=user_id,
                name=user["name"],
                department=user.get("department", "General"),
                punch_type=punch_type,
                status=status,
                confidence=confidence,
                liveness_score=liveness_score,
                snapshot_path=snapshot_path,
                notes=f"Auto biometric match ({round(confidence * 100, 1)}%)",
                recorded_at=attendance_time
            )

            # 6. Update in-memory cooldown timestamp
            self.last_punch_time[user_id] = time.time()

            action_text = "Checked In" if punch_type == "CHECK_IN" else "Checked Out"
            status_text = f" ({status.replace('_', ' ').title()})" if punch_type == "CHECK_IN" else ""

            return {
                "success": True,
                "action": punch_type,
                "status": status,
                "message": f"{user['name']} successfully {action_text}{status_text}",
                "record": record,
                "user": user
            }
