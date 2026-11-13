import os
import random
from datetime import datetime, timedelta, date
import numpy as np

from database.db import init_db, get_db_connection
from database.models import create_user, log_attendance, get_all_users

SAMPLE_USERS = [
    {
        "user_id": "EMP001",
        "name": "Dr. Sarah Chen",
        "department": "AI Research",
        "role": "Lead Scientist",
        "email": "sarah.chen@company.ai",
        "phone": "+1 (555) 019-2834"
    },
    {
        "user_id": "EMP002",
        "name": "Marcus Rodriguez",
        "department": "Engineering",
        "role": "Senior Dev",
        "email": "marcus.r@company.ai",
        "phone": "+1 (555) 018-9921"
    },
    {
        "user_id": "EMP003",
        "name": "Amina Patel",
        "department": "Product Design",
        "role": "UI/UX Designer",
        "email": "amina.patel@company.ai",
        "phone": "+1 (555) 014-7732"
    },
    {
        "user_id": "EMP004",
        "name": "David Kim",
        "department": "Operations",
        "role": "Ops Specialist",
        "email": "david.kim@company.ai",
        "phone": "+1 (555) 012-3341"
    },
    {
        "user_id": "EMP005",
        "name": "Elena Rostova",
        "department": "Cyber Security",
        "role": "SecOps Analyst",
        "email": "elena.r@company.ai",
        "phone": "+1 (555) 017-8845"
    }
]


def seed_database():
    print("Initializing Database...")
    init_db()

    existing_users = get_all_users()
    if not existing_users:
        print("Seeding sample user profiles...")
        for u in SAMPLE_USERS:
            # Generate deterministic unit-normalized 128D embedding vector for demo
            rng = np.random.RandomState(seed=int(u["user_id"][-3:]) * 42)
            raw_emb = rng.randn(128).astype(np.float32)
            emb = raw_emb / np.linalg.norm(raw_emb)

            create_user(
                user_id=u["user_id"],
                name=u["name"],
                department=u["department"],
                role=u["role"],
                email=u["email"],
                phone=u["phone"],
                photo_path=None,
                embedding=emb
            )
        print(f"Created {len(SAMPLE_USERS)} users.")

    # Check if attendance exists
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM attendance")
    count = cur.fetchone()[0]

    if count == 0:
        print("Seeding attendance logs for the past 7 days...")
        today = date.today()
        all_users = get_all_users()

        for day_offset in range(6, -1, -1):
            target_date = today - timedelta(days=day_offset)
            target_date_str = target_date.strftime("%Y-%m-%d")

            for user in all_users:
                # 85% attendance probability
                if random.random() > 0.85 and day_offset > 0:
                    continue

                # 70% chance on-time (between 08:35 and 09:12), 30% late (between 09:16 and 09:45)
                is_on_time = random.random() < 0.75
                if is_on_time:
                    in_hour = 8 if random.random() < 0.4 else 9
                    in_min = random.randint(35, 59) if in_hour == 8 else random.randint(0, 14)
                    status = "ON_TIME"
                else:
                    in_hour = 9
                    in_min = random.randint(16, 45)
                    status = "LATE"

                in_sec = random.randint(10, 55)
                check_in_time = f"{in_hour:02d}:{in_min:02d}:{in_sec:02d}"
                check_in_dt = datetime.strptime(f"{target_date_str} {check_in_time}", "%Y-%m-%d %H:%M:%S")

                confidence = round(random.uniform(0.88, 0.99), 3)

                # Log CHECK_IN
                cur.execute("""
                    INSERT INTO attendance (
                        user_id, name, department, date, time, timestamp,
                        punch_type, status, confidence, liveness_score, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user["user_id"], user["name"], user["department"],
                    target_date_str, check_in_time, check_in_dt.timestamp(),
                    "CHECK_IN", status, confidence, 0.98, "Biometric match"
                ))

                # Log CHECK_OUT (for past days or afternoon today)
                if day_offset > 0 or datetime.now().hour >= 17:
                    out_hour = random.choice([17, 18])
                    out_min = random.randint(0, 45)
                    out_sec = random.randint(10, 55)
                    check_out_time = f"{out_hour:02d}:{out_min:02d}:{out_sec:02d}"
                    check_out_dt = datetime.strptime(f"{target_date_str} {check_out_time}", "%Y-%m-%d %H:%M:%S")
                    out_status = "NORMAL"

                    cur.execute("""
                        INSERT INTO attendance (
                            user_id, name, department, date, time, timestamp,
                            punch_type, status, confidence, liveness_score, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user["user_id"], user["name"], user["department"],
                        target_date_str, check_out_time, check_out_dt.timestamp(),
                        "CHECK_OUT", out_status, confidence, 0.98, "Biometric match"
                    ))

        conn.commit()
        print("Attendance logs successfully seeded.")

    conn.close()
    print("Database is primed and ready!")


if __name__ == "__main__":
    seed_database()
