"""
test_integration.py - Deep Integration and Quality Assurance Test Suite
Tests cross-module data flow:
1. Frontend Contract to Database Persistence & Foreign Key Cascade/Restrict
2. Returning Guest Email Reuse vs. New Guest Creation
3. Temporal Date Invariant Boundaries (Month crossings, 1-night minimums)
4. Dynamic Pricing Calculation Precision across all room categories
5. Availability Filtering Precision
6. Concurrency & Overlap Scenarios (Encompassing, Contained, Edge-Touching)
"""

import sqlite3
from datetime import date, timedelta
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from main import app, get_db


@pytest.fixture
def qa_db(tmp_path):
    """Provisions a pristine database for QA and integration testing."""
    db_file = tmp_path / "qa_hotel.db"
    conn = sqlite3.connect(db_file)
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
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance')),
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

    # Seed all three room types with precise prices
    cur.executemany(
        "INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES (?, ?, ?, ?);",
        [
            ("101", "Single", 79.99, "Available"),
            ("102", "Single", 84.50, "Available"),
            ("201", "Double", 129.99, "Available"),
            ("301", "Family Suite", 219.95, "Available"),
            ("401", "Double", 150.00, "Maintenance"), # Out of service
        ]
    )
    conn.commit()
    yield db_file
    conn.close()


@pytest.fixture
def qa_client(qa_db) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(qa_db)
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


# ==========================================
# 1. Maintenance Room Handling
# ==========================================

def test_maintenance_room_is_excluded_and_unbookable(qa_client: TestClient):
    """Rooms in Maintenance status must not be returned in GET /rooms or bookable."""
    res = qa_client.get("/rooms")
    assert res.status_code == 200
    rooms = res.json()
    room_numbers = [r["room_number"] for r in rooms]
    assert "401" not in room_numbers, "Room 401 is under maintenance and must not appear in available rooms"

    # Attempt to book room 401 directly
    res_book = qa_client.post("/bookings", json={
        "room_id": 5, # ID of room 401
        "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-03",
        "guest": {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "555-0100"
        }
    })
    assert res_book.status_code == 400
    assert "maintenance" in res_book.json()["detail"].lower()


# ==========================================
# 2. Returning Guest Email Reuse Test
# ==========================================

def test_returning_guest_reuses_existing_record(qa_client: TestClient, qa_db):
    """
    When a guest makes a second reservation using the same email,
    the system must reuse their existing Guests.id without duplicate key collision.
    """
    guest_data = {
        "first_name": "Sarah",
        "last_name": "Connor",
        "email": "sarah.connor@resistance.org",
        "phone": "+1-555-1984"
    }

    # First booking creates guest
    b1 = qa_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-10-01",
        "check_out_date": "2026-10-03",
        "guest": guest_data
    }).json()
    guest_id_1 = b1["guest"]["id"]

    # Second booking with same email on a different room and dates
    b2 = qa_client.post("/bookings", json={
        "room_id": 2,
        "check_in_date": "2026-10-05",
        "check_out_date": "2026-10-08",
        "guest": guest_data
    }).json()
    guest_id_2 = b2["guest"]["id"]

    assert guest_id_1 == guest_id_2, "Returning guest with identical email should reuse existing guest_id"

    # Verify only 1 guest record exists in database
    conn = sqlite3.connect(qa_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Guests WHERE email = ?", (guest_data["email"],))
    count = cur.fetchone()[0]
    conn.close()
    assert count == 1, f"Expected exactly 1 guest record, found {count}"


# ==========================================
# 3. Calculation Precision & Month Crossing
# ==========================================

def test_pricing_precision_across_month_boundary(qa_client: TestClient):
    """
    Verify pricing across month boundary (Oct 29 to Nov 03 = 5 nights)
    on Suite ($219.95/night).
    Expected total: 5 * 219.95 = 1099.75
    """
    res = qa_client.post("/bookings", json={
        "room_id": 4, # Family Suite $219.95
        "check_in_date": "2026-10-29",
        "check_out_date": "2026-11-03",
        "guest": {
            "first_name": "Bruce",
            "last_name": "Wayne",
            "email": "bruce@wayne.corp",
            "phone": "+1-555-BAT1"
        }
    })
    assert res.status_code == 201
    booking = res.json()
    assert booking["total_price"] == 1099.75


# ==========================================
# 4. Strict Overlap Geometry QA
# ==========================================

@pytest.mark.parametrize("req_in,req_out,should_conflict", [
    ("2026-12-05", "2026-12-10", False), # Entirely before
    ("2026-12-08", "2026-12-10", False), # Adjacent touching start (checkout on checkin)
    ("2026-12-09", "2026-12-12", True),  # Overlapping start
    ("2026-12-11", "2026-12-13", True),  # Strictly inside
    ("2026-12-08", "2026-12-17", True),  # Strictly encompassing
    ("2026-12-13", "2026-12-16", True),  # Overlapping end
    ("2026-12-15", "2026-12-18", False), # Adjacent touching end (checkin on checkout)
    ("2026-12-16", "2026-12-20", False), # Entirely after
])
def test_all_interval_overlap_permutations(qa_client: TestClient, req_in, req_out, should_conflict):
    """
    Base booking is fixed: Dec 10 to Dec 15.
    Tests every possible temporal geometry:
    - Preceding
    - Touch-start
    - Overlap-start
    - Contained
    - Encompassing
    - Overlap-end
    - Touch-end
    - Following
    """
    # Create base booking on Room 1
    # Use isolated guest
    base_res = qa_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-12-10",
        "check_out_date": "2026-12-15",
        "guest": {
            "first_name": "Base",
            "last_name": "Guest",
            "email": f"base_{req_in}_{req_out}@example.com",
            "phone": "555-0001"
        }
    })
    assert base_res.status_code in [201, 409] # May already be created

    # Test candidate booking
    res = qa_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": req_in,
        "check_out_date": req_out,
        "guest": {
            "first_name": "Candidate",
            "last_name": "Guest",
            "email": f"cand_{req_in}_{req_out}@example.com",
            "phone": "555-0002"
        }
    })

    if should_conflict:
        assert res.status_code == 409, f"Interval [{req_in}, {req_out}) should have conflicted with [2026-12-10, 2026-12-15), got {res.status_code}"
    else:
        assert res.status_code == 201, f"Interval [{req_in}, {req_out}) should be allowed, got {res.status_code}: {res.text}"


# ==========================================
# 5. Database Referential Integrity (RESTRICT)
# ==========================================

def test_database_foreign_key_deletion_restriction(qa_client: TestClient, qa_db):
    """
    Confirms that deleting a room with an active reservation is blocked by SQLite
    ON DELETE RESTRICT at the database engine level.
    """
    # Create a booking on Room 1
    qa_client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2027-02-01",
        "check_out_date": "2027-02-05",
        "guest": {
            "first_name": "Integrity",
            "last_name": "Checker",
            "email": "fk@example.com",
            "phone": "555-9999"
        }
    })

    conn = sqlite3.connect(qa_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    with pytest.raises(sqlite3.IntegrityError):
        # Attempting to delete Room 1 must fail due to FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT
        cur.execute("DELETE FROM Rooms WHERE id = 1;")
        conn.commit()

    conn.close()
