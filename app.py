import os
import io
import time
import base64
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, Request, File, Form, UploadFile, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contextlib import asynccontextmanager
from database.db import init_db, DB_PATH, FACES_DIR, SNAPSHOTS_DIR
from database.models import (
    create_user, get_all_users, get_user_by_id, delete_user,
    get_attendance_logs, get_dashboard_metrics, get_settings, update_settings
)
from database.export_utils import export_to_csv, export_to_excel
from core.face_engine import FaceEngine
from core.attendance_service import AttendanceService

# Paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"

# Global Engine Singletons
engine: Optional[FaceEngine] = None
attendance_service: Optional[AttendanceService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager for startup and shutdown."""
    global engine, attendance_service
    init_db()
    engine = FaceEngine()
    attendance_service = AttendanceService()
    print("AI/ML Attendance Monitoring System started successfully!")
    yield


# Initialize FastAPI App
app = FastAPI(
    title="AI/ML Face Recognition Attendance System",
    description="Enterprise-grade biometric attendance monitoring with deep learning",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and media directories
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# -------------------------------------------------------------
# Frontend View
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Render the single-page application dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------------------------------------------------
# Biometric Recognition Endpoint (Browser WebCam Feed)
# -------------------------------------------------------------
class RecognizeRequest(BaseModel):
    image: str  # Base64 data URL
    threshold: Optional[float] = None
    force_punch_type: Optional[str] = None


@app.post("/api/recognize")
async def recognize_frame(payload: RecognizeRequest):
    """
    Process camera frame sent from browser:
    - Detects faces
    - Extracts 128D embeddings
    - Anti-spoofing verification
    - Logs attendance if recognized
    - Returns bounding boxes, identities, and punch notifications
    """
    global engine, attendance_service
    if engine is None or attendance_service is None:
        raise HTTPException(status_code=500, detail="Face Engine not initialized")

    try:
        # Decode base64 image
        header_data = payload.image
        if "," in header_data:
            header_data = header_data.split(",", 1)[1]
        img_bytes = base64.b64decode(header_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image payload")

        h, w = frame.shape[:2]

        settings = get_settings()
        liveness_enabled = settings.get("liveness_enabled", "true").lower() == "true"
        threshold = payload.threshold if payload.threshold is not None else float(settings.get("similarity_threshold", 0.45))

        detections = engine.process_frame(frame, threshold=threshold, enable_liveness=liveness_enabled)

        processed_faces = []
        punches = []

        for det in detections:
            x, y, bw, bh = det["bbox"]
            status = det["status"]
            user = det["user"]
            similarity = det["similarity"]
            liveness = det["liveness"]
            aligned_face = det.get("aligned_face")

            face_data = {
                "bbox": [x, y, bw, bh],
                "status": status,
                "similarity": similarity,
                "confidence_percent": int(similarity * 100),
                "liveness": liveness,
                "user": user
            }

            # If face is identified and live, process punch event
            if status == "IDENTIFIED" and user:
                punch_res = attendance_service.record_punch(
                    user=user,
                    confidence=similarity,
                    liveness_score=liveness.get("score", 1.0),
                    face_snapshot=aligned_face,
                    force_punch_type=payload.force_punch_type
                )
                face_data["punch"] = punch_res
                punches.append(punch_res)

            processed_faces.append(face_data)

        return {
            "success": True,
            "frame_size": [w, h],
            "faces_count": len(processed_faces),
            "faces": processed_faces,
            "punches": punches
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# -------------------------------------------------------------
# User Enrollment & Management
# -------------------------------------------------------------
@app.post("/api/users/enroll")
async def enroll_user(
    user_id: str = Form(...),
    name: str = Form(...),
    department: str = Form(...),
    role: str = Form("Staff"),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    photo_base64: Optional[str] = Form(None)
):
    """
    Enroll a new user with face biometric vector.
    Accepts either file upload or webcam base64 capture.
    """
    global engine
    if engine is None:
        raise HTTPException(status_code=500, detail="Face Engine not initialized")

    user_id = user_id.strip().upper()
    existing = get_user_by_id(user_id)
    if existing:
        return JSONResponse(status_code=400, content={"success": False, "message": f"User ID '{user_id}' already exists."})

    # Read image
    frame = None
    if photo and photo.filename:
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif photo_base64:
        header_data = photo_base64
        if "," in header_data:
            header_data = header_data.split(",", 1)[1]
        img_bytes = base64.b64decode(header_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None or frame.size == 0:
        return JSONResponse(status_code=400, content={"success": False, "message": "No valid face photo provided."})

    # Detect face
    faces = engine.detect_faces(frame, score_threshold=0.6)
    if faces is None or len(faces) == 0:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No face detected in the image. Please ensure good lighting and look directly at camera."}
        )

    # Pick the most prominent face (largest area)
    best_face = max(faces, key=lambda f: f[2] * f[3])

    # Extract 128D embedding
    aligned_face, feat = engine.extract_face_feature(frame, best_face)

    # Save photo file
    photo_filename = f"{user_id}.jpg"
    photo_path = FACES_DIR / photo_filename
    cv2.imwrite(str(photo_path), aligned_face)
    relative_photo_url = f"/data/faces/{photo_filename}"

    # Insert into Database
    user = create_user(
        user_id=user_id,
        name=name.strip(),
        department=department.strip(),
        role=role.strip() if role else "Staff",
        email=email.strip() if email else None,
        phone=phone.strip() if phone else None,
        photo_path=relative_photo_url,
        embedding=feat
    )

    # Reload FaceEngine vector memory
    engine.reload_known_faces()

    return {
        "success": True,
        "message": f"User '{name}' successfully enrolled!",
        "user": user
    }


@app.get("/api/users")
async def list_users():
    """Get all enrolled active users."""
    users = get_all_users(active_only=True)
    return {"success": True, "users": users, "total": len(users)}


@app.delete("/api/users/{user_id}")
async def remove_user(user_id: str):
    """Delete a user profile and biometric record."""
    global engine
    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove photo if exists
    photo_path = FACES_DIR / f"{user_id}.jpg"
    if photo_path.exists():
        try:
            photo_path.unlink()
        except Exception:
            pass

    if engine:
        engine.reload_known_faces()

    return {"success": True, "message": f"User '{user_id}' deleted successfully."}


# -------------------------------------------------------------
# Attendance Logs & Export
# -------------------------------------------------------------
@app.get("/api/attendance")
async def list_attendance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Query attendance history with flexible filters."""
    logs, total = get_attendance_logs(
        start_date=start_date,
        end_date=end_date,
        department=department,
        user_id=user_id,
        punch_type=punch_type,
        limit=limit,
        offset=offset
    )
    return {
        "success": True,
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/attendance/export")
async def export_attendance(
    format: str = Query("csv", pattern="^(csv|excel)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None
):
    """Export attendance logs as CSV or Excel."""
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")

    if format == "csv":
        buf = export_to_csv(start_date, end_date, department, user_id, punch_type)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_export_{timestamp_str}.csv"}
        )
    else:
        buf = export_to_excel(start_date, end_date, department, user_id, punch_type)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=attendance_export_{timestamp_str}.xlsx"}
        )


# -------------------------------------------------------------
# Analytics & KPI Metrics
# -------------------------------------------------------------
@app.get("/api/analytics")
async def get_analytics(date_str: Optional[str] = None):
    """Get key performance metrics and data for graphs."""
    metrics = get_dashboard_metrics(today_date=date_str)
    return {"success": True, "metrics": metrics}


# -------------------------------------------------------------
# System Configuration Settings
# -------------------------------------------------------------
@app.get("/api/settings")
async def fetch_settings():
    """Retrieve all configurable system settings."""
    return {"success": True, "settings": get_settings()}


@app.post("/api/settings")
async def save_settings(payload: Dict[str, Any]):
    """Update system settings."""
    update_settings(payload)
    return {"success": True, "message": "Settings saved successfully."}


# -------------------------------------------------------------
# USB Camera Server MJPEG Stream (Optional for Server Camera)
# -------------------------------------------------------------
def generate_camera_stream(camera_index: int = 0):
    """Generator for MJPEG video stream from server local camera."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
            frame = cv2.flip(frame, 1)
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not ret:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.04)  # ~25 FPS
    finally:
        cap.release()


@app.get("/video_feed")
def video_feed():
    """MJPEG stream endpoint for server-side USB webcam."""
    settings = get_settings()
    cam_index = int(settings.get("camera_index", "0"))
    return StreamingResponse(
        generate_camera_stream(cam_index),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
