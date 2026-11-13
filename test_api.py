from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_api():
    # 1. Test Home page
    r_home = client.get("/")
    assert r_home.status_code == 200, f"Home failed: {r_home.status_code}"
    assert "AegisFace" in r_home.text
    print("GET /: OK")

    # 2. Test Users list
    r_users = client.get("/api/users")
    assert r_users.status_code == 200
    data_users = r_users.json()
    assert data_users["success"] is True
    print(f"GET /api/users: OK ({len(data_users['users'])} users)")

    # 3. Test Attendance logs
    r_att = client.get("/api/attendance?limit=5")
    assert r_att.status_code == 200
    data_att = r_att.json()
    assert data_att["success"] is True
    print(f"GET /api/attendance: OK ({data_att['total']} total records)")

    # 4. Test Analytics
    r_ana = client.get("/api/analytics")
    assert r_ana.status_code == 200
    data_ana = r_ana.json()
    assert data_ana["success"] is True
    print("GET /api/analytics: OK")

    # 5. Test Settings
    r_set = client.get("/api/settings")
    assert r_set.status_code == 200
    data_set = r_set.json()
    assert data_set["success"] is True
    print("GET /api/settings: OK")

    # 6. Test CSV Export
    r_csv = client.get("/api/attendance/export?format=csv")
    assert r_csv.status_code == 200
    assert len(r_csv.content) > 100
    print("GET /api/attendance/export?format=csv: OK")

    # 7. Test Excel Export
    r_excel = client.get("/api/attendance/export?format=excel")
    assert r_excel.status_code == 200
    assert len(r_excel.content) > 1000
    print("GET /api/attendance/export?format=excel: OK")

    print("\nALL API ENDPOINTS TESTED AND VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
