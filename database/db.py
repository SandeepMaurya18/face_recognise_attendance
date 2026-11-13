import os
import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "attendance.db"
FACES_DIR = DATA_DIR / "faces"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"


def ensure_directories():
    """Ensure data directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    """Get a SQLite database connection with row factory enabled."""
    ensure_directories()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrent read/write efficiency
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    """Initialize database tables with optimal indexing."""
    ensure_directories()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        role TEXT DEFAULT 'Staff',
        email TEXT,
        phone TEXT,
        photo_path TEXT,
        embedding BLOB NOT NULL,
        created_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    """)

    # Attendance logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        timestamp REAL NOT NULL,
        punch_type TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL NOT NULL,
        liveness_score REAL DEFAULT 1.0,
        snapshot_path TEXT,
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Create indexes for fast querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp);")

    # Default Settings
    default_settings = {
        "work_start_time": "09:00",
        "work_end_time": "17:00",
        "grace_minutes": "15",
        "manual_attendance_time": "",
        "similarity_threshold": "0.45",
        "cooldown_seconds": "60",
        "liveness_enabled": "true",
        "camera_index": "0",
        "system_title": "AI Attendance Monitor"
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", (key, val))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
