"""
test_module10.py - Automated Test Suite for Module 10: Guest CRM & Loyalty Engine
Validates:
1. Aggregated CRM metrics calculation (lifetime spend, completed stays, active stays, average spend)
2. VIP Loyalty Tier resolution and dynamic advancement (Standard, Silver, Gold, Platinum)
3. Search filtering by text query (name, email, phone) and VIP tier filter
4. Chronological stay history and folio details retrieval via GET /guests/{id}
5. Guest profile mutation via PATCH /guests/{id} (VIP promotion, preference notes)
6. Duplicate email protection (HTTP 409) and not-found guardrails (HTTP 404)
"""

import sqlite3
from datetime import date
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from database import get_db_connection
from main import app, get_db


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    """Provides isolated test database with initialized schema for Module 10 testing."""
    test_db = tmp_path / "test_module10.db"
    conn = sqlite3.connect(test_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
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
    """)

    cur.execute("""
    CREATE TABLE Rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
        price_per_night REAL NOT NULL CHECK(price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Cleaning')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE Bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date DATE NOT NULL,
        check_out_date DATE NOT NULL,
        total_price REAL NOT NULL CHECK(total_price >= 0),
        booking_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(booking_status IN ('Confirmed', 'Checked-in', 'Checked-out', 'Cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guest_id) REFERENCES Guests(id) ON DELETE CASCADE,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT
    );
    """)

    cur.execute("""
    CREATE TABLE Amenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price REAL NOT NULL CHECK(price >= 0),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
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
    """)

    # Seed test room and amenities
    cur.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('101', 'Single', 100.0, 'Available');")
    cur.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('201', 'Double', 200.0, 'Available');")
    cur.execute("INSERT INTO Amenities (name, price, description) VALUES ('Breakfast', 25.0, 'Morning buffet');")
    cur.execute("INSERT INTO Amenities (name, price, description) VALUES ('Airport Shuttle', 35.0, 'Transfer service');")
    conn.commit()
    conn.close()

    def override_get_db():
        c = sqlite3.connect(test_db)
        c.execute("PRAGMA foreign_keys = ON;")
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_guest_profile_and_crm_defaults(client: TestClient):
    """Verifies direct guest creation via POST /guests with initial CRM default metrics."""
    payload = {
        "first_name": "Alexander",
        "last_name": "Hamilton",
        "email": "a.hamilton@treasury.gov",
        "phone": "+1-555-1789",
        "vip_tier": "Standard",
        "notes": "Prefers quiet room facing courtyard."
    }
    res = client.post("/guests", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["first_name"] == "Alexander"
    assert data["last_name"] == "Hamilton"
    assert data["email"] == "a.hamilton@treasury.gov"
    assert data["vip_tier"] == "Standard"
    assert data["notes"] == "Prefers quiet room facing courtyard."
    assert data["total_bookings"] == 0
    assert data["lifetime_spent"] == 0.0
    assert data["completed_stays"] == 0


def test_list_guests_crm_aggregation(client: TestClient):
    """Verifies that lifetime spend and completed stays are properly aggregated across multiple bookings."""
    # 1. Register Guest
    g_res = client.post("/guests", json={
        "first_name": "Thomas",
        "last_name": "Jefferson",
        "email": "t.jefferson@monticello.org",
        "phone": "+1-555-1776",
        "vip_tier": "Standard",
        "notes": "High floor request"
    })
    guest_id = g_res.json()["id"]

    # 2. Create and complete 3 bookings ($600 total spend -> Silver upgrade)
    # Booking 1: Checked-out ($200)
    b1 = client.post("/bookings", json={
        "guest_id": guest_id,
        "room_id": 1,
        "check_in_date": "2026-05-01",
        "check_out_date": "2026-05-03"
    }).json()
    client.post(f"/bookings/{b1['id']}/check-in")
    client.post(f"/bookings/{b1['id']}/check-out")

    # Booking 2: Checked-out ($400)
    b2 = client.post("/bookings", json={
        "guest_id": guest_id,
        "room_id": 2,
        "check_in_date": "2026-06-01",
        "check_out_date": "2026-06-03"
    }).json()
    client.post(f"/bookings/{b2['id']}/check-in")
    client.post(f"/bookings/{b2['id']}/check-out")

    # 3. Retrieve CRM list
    res = client.get("/guests")
    assert res.status_code == 200
    guests = res.json()
    tj = next(g for g in guests if g["id"] == guest_id)
    assert tj["completed_stays"] == 2
    assert tj["total_bookings"] == 2
    assert tj["lifetime_spent"] == 600.0
    assert tj["average_spend_per_stay"] == 300.0
    assert tj["vip_tier"] == "Silver"  # Dynamically promoted from $600 spend


def test_guest_search_and_tier_filter(client: TestClient):
    """Tests searching guests by partial name/email and filtering by VIP tier."""
    client.post("/guests", json={
        "first_name": "Benjamin",
        "last_name": "Franklin",
        "email": "b.franklin@post.org",
        "phone": "+1-555-7777",
        "vip_tier": "Platinum",
        "notes": "VIP dignitary"
    })
    client.post("/guests", json={
        "first_name": "George",
        "last_name": "Washington",
        "email": "g.washington@mtvernon.org",
        "phone": "+1-555-1799",
        "vip_tier": "Gold",
        "notes": "Presidential suite preferred"
    })

    # Search by query term 'franklin'
    q_res = client.get("/guests?q=franklin")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert len(q_data) == 1
    assert q_data[0]["last_name"] == "Franklin"

    # Filter by VIP tier 'Gold'
    tier_res = client.get("/guests?vip_tier=Gold")
    assert tier_res.status_code == 200
    tier_data = tier_res.json()
    assert any(g["last_name"] == "Washington" for g in tier_data)
    assert all(g["vip_tier"] == "Gold" for g in tier_data)


def test_get_guest_detail_stay_history(client: TestClient):
    """Verifies detailed guest view includes comprehensive stay history."""
    g_res = client.post("/guests", json={
        "first_name": "James",
        "last_name": "Madison",
        "email": "j.madison@virginia.gov",
        "phone": "+1-555-1809"
    })
    guest_id = g_res.json()["id"]

    # Book room
    b_res = client.post("/bookings", json={
        "guest_id": guest_id,
        "room_id": 1,
        "check_in_date": "2026-07-10",
        "check_out_date": "2026-07-12",
        "amenity_ids": [1] # Breakfast $25
    })
    assert b_res.status_code == 201

    # Fetch detail
    detail_res = client.get(f"/guests/{guest_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["first_name"] == "James"
    assert len(detail["stay_history"]) == 1
    booking_history = detail["stay_history"][0]
    assert booking_history["room"]["room_number"] == "101"
    assert len(booking_history["amenities"]) == 1
    assert booking_history["amenities"][0]["name"] == "Breakfast"


def test_update_guest_profile_and_notes(client: TestClient):
    """Verifies updating VIP tier, preference notes, and contact info via PATCH."""
    g_res = client.post("/guests", json={
        "first_name": "John",
        "last_name": "Adams",
        "email": "j.adams@peace.org",
        "phone": "+1-555-1797"
    })
    guest_id = g_res.json()["id"]

    # Update VIP tier and notes
    patch_res = client.patch(f"/guests/{guest_id}", json={
        "vip_tier": "Platinum",
        "notes": "Requires late check-out and extra pillows."
    })
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["vip_tier"] == "Platinum"
    assert updated["notes"] == "Requires late check-out and extra pillows."


def test_guest_email_conflict_and_not_found(client: TestClient):
    """Verifies 409 conflict when duplicate email is registered and 404 for unknown guest."""
    client.post("/guests", json={
        "first_name": "User",
        "last_name": "One",
        "email": "duplicate@example.com",
        "phone": "+1-555-0001"
    })

    # Duplicate creation fails with 409
    res_dup = client.post("/guests", json={
        "first_name": "User",
        "last_name": "Two",
        "email": "duplicate@example.com",
        "phone": "+1-555-0002"
    })
    assert res_dup.status_code == 409

    # Not found on non-existent guest
    assert client.get("/guests/99999").status_code == 404
    assert client.patch("/guests/99999", json={"notes": "test"}).status_code == 404
