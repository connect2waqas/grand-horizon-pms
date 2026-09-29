"""
test_module12.py - Test Suite for Module 12: Enterprise Audit Trail & Operations Ledger
Hotel Management System MVP

Tests verify:
1. Initial system audit logs seeded on database startup.
2. Room operational status mutations record ROOM_STATUS_UPDATED with old/new states.
3. Reservation creation logs BOOKING_CREATED with stay and pricing metadata.
4. Reservation check-in, check-out, and cancellation log respective events.
5. Guest CRM profile creation and updates log GUEST_CREATED and GUEST_UPDATED.
6. Filtering by entity_type, action, and pagination (limit/offset) on GET /audit-logs.
"""

import pytest
import sqlite3
from fastapi.testclient import TestClient

from main import app, get_db


@pytest.fixture
def test_client(tmp_path):
    """
    Creates an isolated test database with all 7 tables and seeds,
    overriding the FastAPI get_db dependency.
    """
    test_db = tmp_path / "test_module12.db"
    conn = sqlite3.connect(test_db, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row

    # Execute DDL
    conn.executescript("""
    CREATE TABLE Guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        vip_tier TEXT NOT NULL DEFAULT 'Standard',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE Rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
        price_per_night REAL NOT NULL CHECK(price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Cleaning')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE Bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date DATE NOT NULL,
        check_out_date DATE NOT NULL,
        total_price REAL NOT NULL CHECK(total_price >= 0),
        booking_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(booking_status IN ('Confirmed', 'Checked-in', 'Checked-out', 'Cancelled')),
        coupon_code TEXT DEFAULT NULL,
        discount_amount REAL NOT NULL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guest_id) REFERENCES Guests(id) ON DELETE CASCADE,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT
    );

    CREATE TABLE Amenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price REAL NOT NULL CHECK(price >= 0),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE BookingAmenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        amenity_id INTEGER NOT NULL,
        price_charged REAL NOT NULL CHECK(price_charged >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE CASCADE,
        FOREIGN KEY (amenity_id) REFERENCES Amenities(id) ON DELETE RESTRICT,
        UNIQUE(booking_id, amenity_id)
    );

    CREATE TABLE Coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        discount_type TEXT NOT NULL CHECK(discount_type IN ('Percentage', 'FixedAmount')),
        discount_value REAL NOT NULL CHECK(discount_value > 0),
        valid_from DATE NOT NULL,
        valid_until DATE NOT NULL,
        min_total REAL NOT NULL DEFAULT 0.0,
        max_uses INTEGER NOT NULL DEFAULT 100,
        used_count INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE AuditLogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL CHECK(entity_type IN ('Room', 'Booking', 'Guest', 'Coupon', 'System')),
        entity_id INTEGER,
        actor TEXT NOT NULL DEFAULT 'Front Desk Agent',
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed baseline fixtures
    conn.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('101', 'Single', 80.0, 'Available');")
    conn.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('102', 'Double', 120.0, 'Available');")
    conn.execute("INSERT INTO Guests (first_name, last_name, email, phone, vip_tier) VALUES ('James', 'Bond', '007@mi6.gov.uk', '+44-7700-900077', 'Platinum');")
    conn.execute("INSERT INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active) VALUES ('WELCOME10', 'Percentage', 10.0, '2026-01-01', '2028-12-31', 50.0, 100, 0, 1);")
    conn.execute("INSERT INTO AuditLogs (action, entity_type, entity_id, actor, details) VALUES ('SYSTEM_INIT', 'System', 0, 'System Admin', 'Bootstrap test database');")
    conn.commit()

    def override_get_db():
        try:
            yield conn
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    conn.close()


def test_audit_logs_endpoint_returns_bootstrap_events(test_client):
    """GET /audit-logs returns initialized system logs."""
    response = test_client.get("/audit-logs")
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "SYSTEM_INIT"
    assert logs[0]["entity_type"] == "System"


def test_room_status_mutation_records_audit_log(test_client):
    """Mutating room status via PATCH /rooms/{id}/status records ROOM_STATUS_UPDATED."""
    patch_res = test_client.patch("/rooms/1/status", json={"status": "Cleaning"})
    assert patch_res.status_code == 200

    audit_res = test_client.get("/audit-logs?entity_type=Room")
    assert audit_res.status_code == 200
    room_logs = audit_res.json()
    assert len(room_logs) >= 1
    latest = room_logs[0]
    assert latest["action"] == "ROOM_STATUS_UPDATED"
    assert latest["entity_id"] == 1
    assert "Available" in latest["details"]
    assert "Cleaning" in latest["details"]


def test_booking_creation_records_audit_log(test_client):
    """Creating a reservation via POST /bookings records BOOKING_CREATED."""
    booking_payload = {
        "room_id": 2,
        "check_in_date": "2026-11-10",
        "check_out_date": "2026-11-12",
        "guest_id": 1,
        "coupon_code": "WELCOME10",
        "apply_dynamic_pricing": False,
    }
    create_res = test_client.post("/bookings", json=booking_payload)
    assert create_res.status_code == 201
    booking_id = create_res.json()["id"]

    audit_res = test_client.get("/audit-logs?action=BOOKING_CREATED")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
    assert logs[0]["entity_id"] == booking_id
    assert "James Bond" in logs[0]["details"]
    assert "WELCOME10" in logs[0]["details"]


def test_checkin_checkout_cancel_lifecycle_records_audit_logs(test_client):
    """Check-in, Check-out, and Cancel record distinct audit events."""
    # 1. Create a booking
    b_res = test_client.post(
        "/bookings",
        json={
            "room_id": 1,
            "check_in_date": "2026-12-01",
            "check_out_date": "2026-12-03",
            "guest_id": 1,
        },
    )
    b_id = b_res.json()["id"]

    # 2. Check-in
    ci_res = test_client.post(f"/bookings/{b_id}/check-in")
    assert ci_res.status_code == 200

    ci_logs = test_client.get(f"/audit-logs?action=CHECK_IN&entity_id={b_id}").json()
    assert len(ci_logs) == 1
    assert ci_logs[0]["action"] == "CHECK_IN"

    # 3. Check-out
    co_res = test_client.post(f"/bookings/{b_id}/check-out")
    assert co_res.status_code == 200

    co_logs = test_client.get(f"/audit-logs?action=CHECK_OUT&entity_id={b_id}").json()
    assert len(co_logs) == 1
    assert co_logs[0]["action"] == "CHECK_OUT"
    assert "Cleaning" in co_logs[0]["details"]

    # 4. Create another booking and cancel it
    b2_res = test_client.post(
        "/bookings",
        json={
            "room_id": 2,
            "check_in_date": "2026-12-10",
            "check_out_date": "2026-12-12",
            "guest_id": 1,
        },
    )
    b2_id = b2_res.json()["id"]

    cancel_res = test_client.post(f"/bookings/{b2_id}/cancel")
    assert cancel_res.status_code == 200

    cancel_logs = test_client.get(f"/audit-logs?action=BOOKING_CANCELLED&entity_id={b2_id}").json()
    assert len(cancel_logs) == 1
    assert cancel_logs[0]["action"] == "BOOKING_CANCELLED"


def test_guest_enrollment_and_update_records_audit_logs(test_client):
    """Guest enrollment and updates log GUEST_CREATED and GUEST_UPDATED."""
    # Create guest
    g_res = test_client.post(
        "/guests",
        json={
            "first_name": "Sherlock",
            "last_name": "Holmes",
            "email": "sherlock@221b.co.uk",
            "phone": "+44-20-7946-0919",
            "vip_tier": "Gold",
            "notes": "Requires quiet suite for deductive work.",
        },
    )
    assert g_res.status_code == 201
    guest_id = g_res.json()["id"]

    g_created_logs = test_client.get(f"/audit-logs?action=GUEST_CREATED&entity_id={guest_id}").json()
    assert len(g_created_logs) == 1
    assert "Sherlock Holmes" in g_created_logs[0]["details"]

    # Update guest
    patch_res = test_client.patch(
        f"/guests/{guest_id}",
        json={"vip_tier": "Platinum", "notes": "Upgraded to Presidential status."},
    )
    assert patch_res.status_code == 200

    g_updated_logs = test_client.get(f"/audit-logs?action=GUEST_UPDATED&entity_id={guest_id}").json()
    assert len(g_updated_logs) == 1
    assert "fields_modified" in g_updated_logs[0]["details"]


def test_audit_log_filtering_and_pagination(test_client):
    """Tests filtering by entity_type and pagination with limit/offset."""
    # Seed multiple room status changes
    for s in ["Cleaning", "Maintenance", "Available"]:
        test_client.patch("/rooms/1/status", json={"status": s})

    # Test limit
    res_limit = test_client.get("/audit-logs?limit=2")
    assert res_limit.status_code == 200
    assert len(res_limit.json()) == 2

    # Test offset
    res_offset = test_client.get("/audit-logs?limit=2&offset=1")
    assert res_offset.status_code == 200
    assert len(res_offset.json()) == 2
    # Ensure items shifted
    assert res_limit.json()[0]["id"] != res_offset.json()[0]["id"]

    # Test entity_type filter
    res_rooms = test_client.get("/audit-logs?entity_type=Room")
    assert res_rooms.status_code == 200
    assert all(log["entity_type"] == "Room" for log in res_rooms.json())
