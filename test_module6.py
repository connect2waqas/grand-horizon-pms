"""
test_module6.py - Automated Test Suite for Module 6: Amenities & Dynamic Pricing
Validates:
1. Amenities catalog endpoint (GET /amenities)
2. Booking creation with dynamic pricing (Base room rate + selected amenities)
3. Many-to-many persistence in BookingAmenities junction table
4. Validation and rejection of non-existent amenity IDs (HTTP 400)
5. Database referential integrity on junction entries
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from main import app, get_db


@pytest.fixture
def m6_db(tmp_path):
    """Provisions an isolated SQLite database with Amenities and BookingAmenities schema."""
    db_file = tmp_path / "test_m6.db"
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Tables
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
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT,
        CHECK (check_out_date > check_in_date)
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

    # Seed Room & Amenities
    cur.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('101', 'Single', 100.00, 'Available');")
    
    amenities = [
        ("Executive Breakfast", 25.00, "Breakfast buffet"),
        ("Airport Shuttle Transfer", 35.00, "Roundtrip transit"),
        ("Spa Pass", 50.00, "Spa and sauna access"),
    ]
    cur.executemany("INSERT INTO Amenities (name, price, description) VALUES (?, ?, ?);", amenities)
    conn.commit()

    yield db_file
    conn.close()


@pytest.fixture
def m6_client(m6_db):
    def override_get_db():
        conn = sqlite3.connect(m6_db)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_get_amenities_catalog(m6_client):
    """Verify that GET /amenities returns the seeded amenities catalog."""
    res = m6_client.get("/amenities")
    assert res.status_code == 200
    catalog = res.json()
    assert len(catalog) == 3
    names = [a["name"] for a in catalog]
    assert "Executive Breakfast" in names
    assert "Airport Shuttle Transfer" in names


def test_booking_without_amenities_charges_base_rate(m6_client):
    """Booking with no amenities charges strictly: nights * price_per_night."""
    res = m6_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-10-01",
        "check_out_date": "2026-10-03", # 2 nights * $100 = $200.00
        "guest": {
            "first_name": "Basic",
            "last_name": "Guest",
            "email": "basic@example.com",
            "phone": "555-0101"
        },
        "amenity_ids": []
    })
    assert res.status_code == 201
    data = res.json()
    assert data["total_price"] == 200.00
    assert data["amenities"] == []


def test_booking_with_amenities_calculates_dynamic_price_and_persists_junction(m6_client, m6_db):
    """
    Booking with Breakfast ($25.00) and Spa ($50.00) on a 2-night stay ($200.00 base):
    Expected total price = 200.00 + 25.00 + 50.00 = $275.00.
    Junction table BookingAmenities must contain 2 rows.
    """
    res = m6_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-10-05",
        "check_out_date": "2026-10-07", # 2 nights @ $100 = $200
        "guest": {
            "first_name": "VIP",
            "last_name": "Guest",
            "email": "vip@example.com",
            "phone": "555-0199"
        },
        "amenity_ids": [1, 3] # Breakfast ($25) + Spa ($50)
    })
    assert res.status_code == 201
    booking = res.json()

    assert booking["total_price"] == 275.00
    assert len(booking["amenities"]) == 2
    amenity_names = [a["name"] for a in booking["amenities"]]
    assert "Executive Breakfast" in amenity_names
    assert "Spa Pass" in amenity_names

    # Direct database junction verification
    conn = sqlite3.connect(m6_db)
    cur = conn.cursor()
    cur.execute("SELECT amenity_id, price_charged FROM BookingAmenities WHERE booking_id = ? ORDER BY amenity_id;", (booking["id"],))
    junction_rows = cur.fetchall()
    conn.close()

    assert len(junction_rows) == 2
    assert junction_rows[0] == (1, 25.00)
    assert junction_rows[1] == (3, 50.00)


def test_booking_with_invalid_amenity_id_fails(m6_client):
    """Requesting an invalid amenity ID must return HTTP 400 Bad Request."""
    res = m6_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-10-10",
        "check_out_date": "2026-10-12",
        "guest": {
            "first_name": "Error",
            "last_name": "Tester",
            "email": "error@example.com",
            "phone": "555-0999"
        },
        "amenity_ids": [9999] # Non-existent
    })
    assert res.status_code == 400
    assert "not found" in res.json()["detail"].lower()


def test_amenity_deletion_restricted_when_booked(m6_client, m6_db):
    """Confirms ON DELETE RESTRICT on Amenities when referenced in BookingAmenities."""
    # Create booking with amenity 1
    m6_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-10-15",
        "check_out_date": "2026-10-17",
        "guest": {
            "first_name": "FK",
            "last_name": "Tester",
            "email": "fk_test@example.com",
            "phone": "555-1122"
        },
        "amenity_ids": [1]
    })

    conn = sqlite3.connect(m6_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Attempt to delete Amenity 1 directly
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("DELETE FROM Amenities WHERE id = 1;")
        conn.commit()

    conn.close()
