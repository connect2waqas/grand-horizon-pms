"""
test_main.py - Automated Testing Suite for Hotel Management System
Module 5: Automated Testing with Pytest

This suite validates business logic invariants, data integrity, and API contracts
in an isolated test database environment using FastAPI's dependency injection overrides.
"""

import sqlite3
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from main import app, get_db


# ==========================================
# Test Fixtures & Isolated Environment
# ==========================================

@pytest.fixture
def test_db(tmp_path):
    """
    Creates an isolated SQLite test database for each test session or function.
    Applies strict PRAGMA foreign_keys and schema migrations.
    """
    db_path = tmp_path / "test_hotel.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Schema
    cursor.execute("""
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

    cursor.execute("""
    CREATE TABLE Rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
        price_per_night REAL NOT NULL CHECK(price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
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

    # Seed 5 isolated test rooms
    sample_rooms = [
        ("101", "Single", 80.00, "Available"),
        ("102", "Single", 85.00, "Available"),
        ("201", "Double", 130.00, "Available"),
        ("202", "Double", 140.00, "Available"),
        ("301", "Family Suite", 220.00, "Available"),
    ]
    cursor.executemany(
        "INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES (?, ?, ?, ?);",
        sample_rooms
    )
    conn.commit()

    yield db_path
    conn.close()


@pytest.fixture
def client(test_db) -> Generator[TestClient, None, None]:
    """
    TestClient fixture configured with FastAPI dependency overrides
    pointing all route queries to the isolated test database.
    """
    def override_get_db() -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(test_db)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ==========================================
# Core Business Logic Test Cases
# ==========================================

def test_get_rooms_initial_catalog(client: TestClient):
    """
    Verifies that the catalog endpoint lists all 5 seeded available rooms.
    """
    response = client.get("/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert len(rooms) == 5
    room_numbers = [r["room_number"] for r in rooms]
    assert "101" in room_numbers
    assert "301" in room_numbers


def test_create_booking_success(client: TestClient):
    """
    Verifies successful reservation flow:
    - Automatically creates guest profile
    - Server calculates total price accurately (2 nights * $80 = $160)
    - Returns 201 Created with Confirmed status
    """
    payload = {
        "room_id": 1,
        "check_in_date": "2026-10-10",
        "check_out_date": "2026-10-12",
        "guest": {
            "first_name": "Eleanor",
            "last_name": "Vance",
            "email": "eleanor.vance@example.com",
            "phone": "+1-555-0199"
        }
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 201
    booking = response.json()
    assert booking["id"] == 1
    assert booking["total_price"] == 160.00
    assert booking["booking_status"] == "Confirmed"
    assert booking["guest"]["email"] == "eleanor.vance@example.com"
    assert booking["room"]["room_number"] == "101"


def test_double_booking_same_dates_fails(client: TestClient):
    """
    CRITICAL INVARIANT TEST:
    Verifies that attempting to book a room for the exact same date range
    as an existing booking fails with HTTP 409 Conflict.
    """
    # 1. First booking succeeds
    first_booking = {
        "room_id": 1,
        "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-05",
        "guest": {
            "first_name": "Arthur",
            "last_name": "Dent",
            "email": "arthur.dent@example.com",
            "phone": "+1-555-4242"
        }
    }
    res1 = client.post("/bookings", json=first_booking)
    assert res1.status_code == 201

    # 2. Second booking on the exact same room and dates MUST FAIL
    second_booking = {
        "room_id": 1,
        "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-05",
        "guest": {
            "first_name": "Ford",
            "last_name": "Prefect",
            "email": "ford.prefect@example.com",
            "phone": "+1-555-9999"
        }
    }
    res2 = client.post("/bookings", json=second_booking)
    assert res2.status_code == 409
    assert "unavailable" in res2.json()["detail"].lower()


def test_double_booking_overlapping_dates_fails(client: TestClient):
    """
    Verifies that partial date overlaps on the same room are also rejected with HTTP 409.
    Existing booking: Nov 10 to Nov 15
    New attempt:      Nov 12 to Nov 17 (overlaps Nov 12-15)
    """
    client.post("/bookings", json={
        "room_id": 2,
        "check_in_date": "2026-11-10",
        "check_out_date": "2026-11-15",
        "guest": {
            "first_name": "Tricia",
            "last_name": "McMillan",
            "email": "trillian@example.com",
            "phone": "+1-555-7777"
        }
    })

    conflict_attempt = {
        "room_id": 2,
        "check_in_date": "2026-11-12",
        "check_out_date": "2026-11-17",
        "guest": {
            "first_name": "Zaphod",
            "last_name": "Beeblebrox",
            "email": "zaphod@example.com",
            "phone": "+1-555-8888"
        }
    }
    response = client.post("/bookings", json=conflict_attempt)
    assert response.status_code == 409
    assert "conflicting booking exists" in response.json()["detail"].lower()


def test_adjacent_back_to_back_bookings_succeed(client: TestClient):
    """
    Verifies that back-to-back bookings (check-in on the exact day another guest checks out)
    succeed without false conflict.
    Booking A: Nov 20 to Nov 23
    Booking B: Nov 23 to Nov 26
    """
    res_a = client.post("/bookings", json={
        "room_id": 3,
        "check_in_date": "2026-11-20",
        "check_out_date": "2026-11-23",
        "guest": {
            "first_name": "Guest",
            "last_name": "One",
            "email": "guest1@example.com",
            "phone": "+1-555-1111"
        }
    })
    assert res_a.status_code == 201

    res_b = client.post("/bookings", json={
        "room_id": 3,
        "check_in_date": "2026-11-23",
        "check_out_date": "2026-11-26",
        "guest": {
            "first_name": "Guest",
            "last_name": "Two",
            "email": "guest2@example.com",
            "phone": "+1-555-2222"
        }
    })
    assert res_b.status_code == 201, f"Expected 201 for back-to-back check-in, got {res_b.status_code}: {res_b.text}"


def test_different_rooms_same_dates_succeed(client: TestClient):
    """
    Verifies that different rooms can be booked for the same dates concurrently.
    """
    res_room1 = client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-12-01",
        "check_out_date": "2026-12-05",
        "guest": {
            "first_name": "Guest",
            "last_name": "Alpha",
            "email": "alpha@example.com",
            "phone": "+1-555-3333"
        }
    })
    assert res_room1.status_code == 201

    res_room2 = client.post("/bookings", json={
        "room_id": 2,
        "check_in_date": "2026-12-01",
        "check_out_date": "2026-12-05",
        "guest": {
            "first_name": "Guest",
            "last_name": "Beta",
            "email": "beta@example.com",
            "phone": "+1-555-4444"
        }
    })
    assert res_room2.status_code == 201


def test_booking_invalid_date_range_fails(client: TestClient):
    """
    Verifies that checkout on or before checkin is rejected at the validation layer (HTTP 422).
    """
    response = client.post("/bookings", json={
        "room_id": 1,
        "check_in_date": "2026-12-10",
        "check_out_date": "2026-12-08",
        "guest": {
            "first_name": "Time",
            "last_name": "Traveler",
            "email": "timetraveler@example.com",
            "phone": "+1-555-0000"
        }
    })
    assert response.status_code == 422


def test_booking_non_existent_room_fails(client: TestClient):
    """
    Verifies that attempting to book a room that does not exist returns HTTP 404.
    """
    response = client.post("/bookings", json={
        "room_id": 9999,
        "check_in_date": "2026-12-20",
        "check_out_date": "2026-12-25",
        "guest": {
            "first_name": "Lost",
            "last_name": "Traveler",
            "email": "lost@example.com",
            "phone": "+1-555-1212"
        }
    })
    assert response.status_code == 404
