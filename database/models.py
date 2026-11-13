import sqlite3
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from database.db import get_db_connection


# -------------------------------------------------------------
# Vector Serialization Utilities
# -------------------------------------------------------------
def embedding_to_blob(embedding: np.ndarray) -> bytes:
    """Convert numpy float32 array to binary blob."""
    return np.asarray(embedding, dtype=np.float32).tobytes()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    """Convert binary blob back to numpy float32 array."""
    return np.frombuffer(blob, dtype=np.float32)


# -------------------------------------------------------------
# User Repository
# -------------------------------------------------------------
def create_user(
    user_id: str,
    name: str,
    department: str,
    role: str,
    email: Optional[str],
    phone: Optional[str],
    photo_path: Optional[str],
    embedding: np.ndarray
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    blob = embedding_to_blob(embedding)

    cursor.execute("""
        INSERT INTO users (user_id, name, department, role, email, phone, photo_path, embedding, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (user_id, name, department, role, email, phone, photo_path, blob, now_iso))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "department": department,
        "role": role,
        "email": email,
        "phone": phone,
        "photo_path": photo_path,
        "created_at": now_iso,
        "is_active": 1
    }


def get_all_users(active_only: bool = True) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, user_id, name, department, role, email, phone, photo_path, created_at, is_active FROM users"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name ASC"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_users_with_embeddings() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, name, department, role, photo_path, embedding FROM users WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()

    users = []
    for row in rows:
        users.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "department": row["department"],
            "role": row["role"],
            "photo_path": row["photo_path"],
            "embedding": blob_to_embedding(row["embedding"])
        })
    return users


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, name, department, role, email, phone, photo_path, created_at, is_active FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def update_user(
    user_id: str,
    name: Optional[str] = None,
    department: Optional[str] = None,
    role: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    photo_path: Optional[str] = None,
    embedding: Optional[np.ndarray] = None
) -> bool:
    """Update existing user record in database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if department is not None:
        updates.append("department = ?")
        params.append(department.strip())
    if role is not None:
        updates.append("role = ?")
        params.append(role.strip())
    if email is not None:
        updates.append("email = ?")
        params.append(email.strip())
    if phone is not None:
        updates.append("phone = ?")
        params.append(phone.strip())
    if photo_path is not None:
        updates.append("photo_path = ?")
        params.append(photo_path)
    if embedding is not None:
        updates.append("embedding = ?")
        params.append(embedding_to_blob(embedding))

    if not updates:
        conn.close()
        return False

    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
    cursor.execute(sql, params)
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected



# -------------------------------------------------------------
# Attendance Repository
# -------------------------------------------------------------
def log_attendance(
    user_id: str,
    name: str,
    department: str,
    punch_type: str,
    status: str,
    confidence: float,
    liveness_score: float = 1.0,
    snapshot_path: Optional[str] = None,
    notes: Optional[str] = None,
    recorded_at: Optional[datetime] = None
) -> Dict[str, Any]:
    now = recorded_at or datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    timestamp = now.timestamp()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attendance (
            user_id, name, department, date, time, timestamp,
            punch_type, status, confidence, liveness_score, snapshot_path, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, name, department, date_str, time_str, timestamp,
        punch_type, status, float(confidence), float(liveness_score), snapshot_path, notes
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "department": department,
        "date": date_str,
        "time": time_str,
        "timestamp": timestamp,
        "punch_type": punch_type,
        "status": status,
        "confidence": confidence,
        "liveness_score": liveness_score,
        "snapshot_path": snapshot_path,
        "notes": notes
    }


def get_user_today_punches(user_id: str, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND date = ?
        ORDER BY timestamp ASC
    """, (user_id, date_str))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_user_punch(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_attendance_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    punch_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if department:
        conditions.append("department = ?")
        params.append(department)
    if user_id:
        conditions.append("(user_id LIKE ? OR name LIKE ?)")
        params.append(f"%{user_id}%")
        params.append(f"%{user_id}%")
    if punch_type:
        conditions.append("punch_type = ?")
        params.append(punch_type)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Total count query
    count_sql = f"SELECT COUNT(*) FROM attendance {where_clause}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]

    # Data query
    data_sql = f"""
        SELECT * FROM attendance
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_sql, params + [limit, offset])
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows], total


# -------------------------------------------------------------
# Analytics Repository
# -------------------------------------------------------------
def get_dashboard_metrics(today_date: Optional[str] = None) -> Dict[str, Any]:
    if not today_date:
        today_date = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total active users
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    total_users = cursor.fetchone()[0]

    # Distinct users checked in today
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM attendance WHERE date = ?", (today_date,))
    present_today = cursor.fetchone()[0]

    # On-time vs Late today (for initial CHECK_IN of each user)
    cursor.execute("""
        SELECT status, COUNT(*) FROM (
            SELECT user_id, status FROM attendance
            WHERE date = ? AND punch_type = 'CHECK_IN'
            GROUP BY user_id
        )
        GROUP BY status
    """, (today_date,))
    status_counts = dict(cursor.fetchall())
    on_time = status_counts.get("ON_TIME", 0)
    late = status_counts.get("LATE", 0)

    # Attendance rate
    rate = round((present_today / total_users * 100), 1) if total_users > 0 else 0.0

    # Department breakdown today
    cursor.execute("""
        SELECT department, COUNT(DISTINCT user_id) as count
        FROM attendance
        WHERE date = ?
        GROUP BY department
    """, (today_date,))
    dept_breakdown = [dict(row) for row in cursor.fetchall()]

    # Hourly check-in distribution today
    cursor.execute("""
        SELECT substr(time, 1, 2) as hour, COUNT(*) as count
        FROM attendance
        WHERE date = ? AND punch_type = 'CHECK_IN'
        GROUP BY hour
        ORDER BY hour ASC
    """, (today_date,))
    hourly_distribution = [dict(row) for row in cursor.fetchall()]

    # Past 7 days attendance trend
    cursor.execute("""
        SELECT date, COUNT(DISTINCT user_id) as count
        FROM attendance
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
    """)
    recent_trend = [dict(row) for row in cursor.fetchall()]
    recent_trend.reverse()

    conn.close()

    return {
        "total_users": total_users,
        "present_today": present_today,
        "absent_today": max(0, total_users - present_today),
        "attendance_rate": rate,
        "on_time_today": on_time,
        "late_today": late,
        "department_breakdown": dept_breakdown,
        "hourly_distribution": hourly_distribution,
        "recent_trend": recent_trend
    }


# -------------------------------------------------------------
# Settings Repository
# -------------------------------------------------------------
def get_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()
    return settings


def update_settings(updates: Dict[str, str]):
    conn = get_db_connection()
    cursor = conn.cursor()
    for key, val in updates.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()
