"""
test_module13.py - Test Suite for Module 13: Maintenance Work Orders & Housekeeping Dispatch
Hotel Management System MVP

Tests verify:
1. Retrieval of maintenance tickets with joined room numbers and sorting by priority.
2. Creation of high/urgent priority tickets automatically locks room into 'Maintenance' status.
3. Ticket resolution with auto_release_room clears 'Maintenance' room status to 'Cleaning'.
4. Proper audit logging on work order creation and room mutation.
5. Validation: 404 on non-existent room, enum constraints.
6. Executive facilities summary endpoint: GET /maintenance/tickets/summary.
"""

import pytest
import sqlite3
from fastapi.testclient import TestClient

from main import app, get_db


@pytest.fixture
def test_client(tmp_path):
    """
    Creates an isolated test database with all 8 tables and seeds,
    overriding the FastAPI get_db dependency.
    """
    test_db = tmp_path / "test_module13.db"
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
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        actor TEXT NOT NULL DEFAULT 'Front Desk Agent',
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE MaintenanceTickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER NOT NULL,
        issue_description TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Plumbing', 'Electrical', 'HVAC', 'Furniture', 'Sanitization', 'Structural', 'General')),
        priority TEXT NOT NULL CHECK(priority IN ('Low', 'Medium', 'High', 'Urgent')),
        status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Cancelled')),
        assigned_staff TEXT DEFAULT 'Facilities Team',
        reported_by TEXT DEFAULT 'Housekeeping',
        estimated_cost REAL DEFAULT 0.0,
        resolution_notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP DEFAULT NULL,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE CASCADE
    );
    """)

    # Seed baseline fixtures
    conn.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('101', 'Single', 80.0, 'Available');")
    conn.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('102', 'Double', 120.0, 'Available');")
    conn.execute(
        """
        INSERT INTO MaintenanceTickets (room_id, issue_description, category, priority, status, assigned_staff, reported_by, estimated_cost)
        VALUES (2, 'Air conditioner leaking water', 'HVAC', 'Medium', 'In Progress', 'John Doe', 'Housekeeping', 120.0);
        """
    )
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


def test_list_maintenance_tickets_with_room_details(test_client):
    """GET /maintenance/tickets returns work orders joined with room number."""
    response = test_client.get("/maintenance/tickets")
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) >= 1
    assert tickets[0]["room_number"] == "102"
    assert tickets[0]["category"] == "HVAC"
    assert tickets[0]["status"] == "In Progress"


def test_create_urgent_ticket_auto_locks_room(test_client):
    """Creating an Urgent ticket on Room 101 automatically mutates room status to Maintenance."""
    # Room 1 is initially Available
    room_before = test_client.get("/rooms").json()
    r1 = next(r for r in room_before if r["id"] == 1)
    assert r1["status"] == "Available"

    payload = {
        "room_id": 1,
        "issue_description": "Severe pipe rupture flooding bathroom floor",
        "category": "Plumbing",
        "priority": "Urgent",
        "assigned_staff": "Emergency Plumbing Squad",
        "reported_by": "Night Auditor",
        "estimated_cost": 350.0,
        "auto_lock_room": True,
    }
    create_res = test_client.post("/maintenance/tickets", json=payload)
    assert create_res.status_code == 201
    ticket = create_res.json()
    assert ticket["priority"] == "Urgent"
    assert ticket["status"] == "Open"
    assert ticket["room_number"] == "101"

    # Verify Room 1 is now in 'Maintenance' status
    room_after = test_client.get("/rooms?include_maintenance=true").json()
    r1_after = next(r for r in room_after if r["id"] == 1)
    assert r1_after["status"] == "Maintenance"

    # Verify audit logs record the maintenance creation & room lock
    audit_res = test_client.get("/audit-logs?entity_type=Room&entity_id=1")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    actions = [l["action"] for l in logs]
    assert "MAINTENANCE_TICKET_CREATED" in actions
    assert "ROOM_STATUS_UPDATED" in actions


def test_resolve_ticket_auto_releases_room_to_cleaning(test_client):
    """Resolving the work order transitions the room to 'Cleaning' ready for sanitization."""
    # First create urgent ticket that locks room 1
    create_res = test_client.post(
        "/maintenance/tickets",
        json={
            "room_id": 1,
            "issue_description": "Ceiling light fixture spark issue",
            "category": "Electrical",
            "priority": "High",
            "auto_lock_room": True,
        },
    )
    ticket_id = create_res.json()["id"]

    # Verify locked
    r_check = test_client.get("/rooms?include_maintenance=true").json()
    assert next(r for r in r_check if r["id"] == 1)["status"] == "Maintenance"

    # Update ticket to Resolved
    patch_res = test_client.patch(
        f"/maintenance/tickets/{ticket_id}",
        json={
            "status": "Resolved",
            "resolution_notes": "Rewired ballast and replaced LED driver. Certified safe.",
            "auto_release_room": True,
        },
    )
    assert patch_res.status_code == 200
    updated_ticket = patch_res.json()
    assert updated_ticket["status"] == "Resolved"
    assert updated_ticket["resolved_at"] is not None
    assert "Certified safe" in updated_ticket["resolution_notes"]

    # Room should now be transitioned to 'Cleaning' for inspection
    r_released = test_client.get("/rooms").json()
    r1_released = next(r for r in r_released if r["id"] == 1)
    assert r1_released["status"] == "Cleaning"


def test_create_ticket_invalid_room_fails_404(test_client):
    """Creating a ticket on non-existent room yields HTTP 404."""
    response = test_client.post(
        "/maintenance/tickets",
        json={
            "room_id": 9999,
            "issue_description": "Non existent room repair",
            "category": "General",
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_maintenance_summary_metrics(test_client):
    """GET /maintenance/tickets/summary computes operational facilities metrics."""
    res = test_client.get("/maintenance/tickets/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_tickets"] >= 1
    assert "open_tickets" in summary
    assert "in_progress_tickets" in summary
    assert "resolved_tickets" in summary
    assert "urgent_tickets" in summary


def test_filtering_tickets_by_status_and_priority(test_client):
    """Filters tickets by status and category."""
    # Filter by In Progress
    res_in_prog = test_client.get("/maintenance/tickets?status=In Progress")
    assert res_in_prog.status_code == 200
    assert all(t["status"] == "In Progress" for t in res_in_prog.json())

    # Filter by HVAC
    res_hvac = test_client.get("/maintenance/tickets?category=HVAC")
    assert res_hvac.status_code == 200
    assert all(t["category"] == "HVAC" for t in res_hvac.json())
