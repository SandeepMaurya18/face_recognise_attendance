import time
import sys
import os
from datetime import datetime
from typing import Dict, Any

import cv2
import numpy as np

# Windows beep sound
try:
    import winsound
    def play_chime(success: bool = True):
        if success:
            winsound.Beep(1200, 100)
            winsound.Beep(1600, 150)
        else:
            winsound.Beep(400, 200)
except ImportError:
    def play_chime(success: bool = True):
        pass

from core.face_engine import FaceEngine
from core.attendance_service import AttendanceService
from database.models import get_settings


def draw_hud_box(img, x, y, w, h, color, label, subtitle=None, score=None, is_live=True):
    """Draw a biometric HUD style bounding box with glowing corners and info tag."""
    line_len = min(25, int(w * 0.25))
    thickness = 2
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 1)

    # Corner brackets
    # Top-Left
    cv2.line(img, (x, y), (x + line_len, y), color, thickness + 1)
    cv2.line(img, (x, y), (x, y + line_len), color, thickness + 1)
    # Top-Right
    cv2.line(img, (x + w, y), (x + w - line_len, y), color, thickness + 1)
    cv2.line(img, (x + w, y), (x + w, y + line_len), color, thickness + 1)
    # Bottom-Left
    cv2.line(img, (x, y + h), (x + line_len, y + h), color, thickness + 1)
    cv2.line(img, (x, y + h), (x, y + h - line_len), color, thickness + 1)
    # Bottom-Right
    cv2.line(img, (x + w, y + h), (x + w - line_len, y + h), color, thickness + 1)
    cv2.line(img, (x + w, y + h), (x + w, y + h - line_len), color, thickness + 1)

    # Tag background
    tag_h = 34 if subtitle else 22
    tag_w = max(140, int(w * 1.1))
    tag_y = max(tag_h + 5, y - 5)

    # Semi-transparent pill background
    overlay = img.copy()
    cv2.rectangle(overlay, (x, tag_y - tag_h), (x + tag_w, tag_y), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    # Border for tag
    cv2.rectangle(img, (x, tag_y - tag_h), (x + tag_w, tag_y), color, 1)

    # Text
    score_str = f" [{int(score * 100)}%]" if score else ""
    cv2.putText(img, f"{label}{score_str}", (x + 6, tag_y - (18 if subtitle else 6)),
                cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    if subtitle:
        live_str = "LIVE" if is_live else "SPOOF"
        cv2.putText(img, f"{subtitle} | {live_str}", (x + 6, tag_y - 5),
                    cv2.FONT_HERSHEY_DUPLEX, 0.35, (148, 163, 184), 1, cv2.LINE_AA)


def run_desktop_kiosk():
    print("=" * 60)
    print(" AI/ML FACE RECOGNITION ATTENDANCE - DESKTOP KIOSK")
    print("=" * 60)

    settings = get_settings()
    cam_index = int(settings.get("camera_index", "0"))
    threshold = float(settings.get("similarity_threshold", "0.45"))
    liveness_enabled = settings.get("liveness_enabled", "true").lower() == "true"

    print(f"Initializing camera device #{cam_index}...")
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)

    if not cap.isOpened():
        print(f"Warning: Could not open camera #{cam_index}. Trying camera #0...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: No webcam detected. Exiting desktop kiosk.")
            return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    engine = FaceEngine()
    attendance_service = AttendanceService()

    window_name = "AI Face Attendance Kiosk - [Press 'Q' to Quit | 'F' for Fullscreen]"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    fps = 0.0
    prev_time = time.time()
    last_banner_msg = "Scanner Ready"
    last_banner_time = time.time()
    banner_color = (74, 222, 128)  # Green

    fullscreen = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        # Flip horizontally for natural mirror feel
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        curr_time = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / (curr_time - prev_time + 1e-6))
        prev_time = curr_time

        # Process detections
        detections = engine.process_frame(frame, threshold=threshold, enable_liveness=liveness_enabled)

        for det in detections:
            x, y, bw, bh = det["bbox"]
            status = det["status"]
            user = det["user"]
            similarity = det["similarity"]
            liveness = det["liveness"]
            is_live = liveness.get("is_live", True)

            # Facial landmarks
            if "landmarks" in det:
                for pt in det["landmarks"]:
                    cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, (0, 255, 255), -1)

            if status == "IDENTIFIED" and user:
                color = (74, 222, 128)  # Neon Green
                label = user["name"]
                subtitle = user["department"]

                # Trigger punch
                face_crop = det.get("aligned_face")
                punch_res = attendance_service.record_punch(
                    user=user,
                    confidence=similarity,
                    liveness_score=liveness.get("score", 1.0),
                    face_snapshot=face_crop
                )

                if punch_res["success"]:
                    play_chime(True)
                    last_banner_msg = punch_res["message"]
                    banner_color = (74, 222, 128)
                    last_banner_time = time.time()
                elif punch_res["action"] == "COOLDOWN_ACTIVE":
                    # Only show once
                    if time.time() - last_banner_time > 3.0:
                        last_banner_msg = f"{user['name']} (Logged: {punch_res['cooldown_remaining']}s cooldown)"
                        banner_color = (96, 165, 250)
                        last_banner_time = time.time()

            elif status == "SPOOF_REJECTED":
                color = (0, 0, 255)  # Red
                label = "ANTI-SPOOF ALERT"
                subtitle = liveness.get("reason", "Photo Spoof")
                if time.time() - last_banner_time > 2.0:
                    play_chime(False)
                    last_banner_msg = "WARNING: Spoof Attempt Rejected"
                    banner_color = (0, 0, 255)
                    last_banner_time = time.time()
            else:
                color = (148, 163, 184)  # Slate Gray
                label = "Unknown Face"
                subtitle = "Not Registered"

            draw_hud_box(frame, x, y, bw, bh, color, label, subtitle, similarity, is_live)

        # Top Bar HUD
        top_bar = frame.copy()
        cv2.rectangle(top_bar, (0, 0), (w, 55), (15, 23, 42), -1)
        cv2.addWeighted(top_bar, 0.85, frame, 0.15, 0, frame)

        # System Title & Live Clock
        clock_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, "AI ATTENDANCE KIOSK", (20, 35), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, clock_str, (w - 240, 35), cv2.FONT_HERSHEY_DUPLEX, 0.55, (148, 163, 184), 1, cv2.LINE_AA)
        cv2.putText(frame, f"FPS: {int(fps)}", (w - 340, 35), cv2.FONT_HERSHEY_DUPLEX, 0.55, (74, 222, 128), 1, cv2.LINE_AA)

        # Notification Banner at bottom
        if time.time() - last_banner_time < 4.0:
            bot_bar = frame.copy()
            cv2.rectangle(bot_bar, (0, h - 50), (w, h), (15, 23, 42), -1)
            cv2.addWeighted(bot_bar, 0.85, frame, 0.15, 0, frame)
            cv2.rectangle(frame, (0, h - 50), (w, h - 47), banner_color, -1)
            cv2.putText(frame, last_banner_msg, (25, h - 18), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # 'q' or Esc
            break
        elif key == ord('f'):  # Toggle fullscreen
            fullscreen = not fullscreen
            prop = cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, prop)

    cap.release()
    cv2.destroyAllWindows()
    print("Desktop Kiosk terminated.")


if __name__ == "__main__":
    run_desktop_kiosk()
