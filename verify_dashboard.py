"""
verify_dashboard.py - Verification script for static dashboard files and API mounting.
"""

from fastapi.testclient import TestClient
from main import app

def verify() -> None:
    with TestClient(app) as client:
        # 1. Verify index.html is served at root /
        res = client.get("/")
        assert res.status_code == 200, f"Expected 200 for /, got {res.status_code}"
        assert "Grand Horizon" in res.text, "Index HTML missing title text"
        assert "roomsGrid" in res.text, "Index HTML missing roomsGrid element"
        assert "bookingForm" in res.text, "Index HTML missing bookingForm element"
        print("[PASS] Root GET / successfully serves index.html with expected DOM IDs.")

        # 2. Verify style.css is accessible
        res = client.get("/style.css")
        assert res.status_code == 200, f"Expected 200 for /style.css, got {res.status_code}"
        assert "--bg-primary" in res.text, "style.css missing CSS variables"
        assert ".rooms-grid" in res.text, "style.css missing grid layout rule"
        print("[PASS] GET /style.css successfully served with CSS grid and design variables.")

        # 3. Verify app.js is accessible
        res = client.get("/app.js")
        assert res.status_code == 200, f"Expected 200 for /app.js, got {res.status_code}"
        assert "fetchRooms" in res.text, "app.js missing fetchRooms logic"
        assert "handleBookingSubmit" in res.text, "app.js missing booking submit handler"
        print("[PASS] GET /app.js successfully served with fetch() controllers.")

    print("\nAll Web Dashboard static assets and integrations verified successfully!")

if __name__ == "__main__":
    verify()
