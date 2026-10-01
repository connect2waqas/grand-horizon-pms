"""
test_module2_deepening.py - Automated Test Suite for Module 2 Deepening
Focus: Reservation & Booking Engine Deepening (Guaranteed vs Non-guaranteed holds,
ETA/arrival times, special guest requests, max capacity enforcement, and intelligent room auto-assignment).
"""

import random
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_create_booking_with_deepened_reservation_fields(client):
    """Verify creating a reservation with guarantee type, ETA, party count, and special requests."""
    # Ensure Room 1 is available
    client.patch("/rooms/1/status", json={"status": "Available"})

    offset = random.randint(20000, 60000)
    check_in = (date.today() + timedelta(days=offset)).isoformat()
    check_out = (date.today() + timedelta(days=offset + 3)).isoformat()

    payload = {
        "room_id": 1,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": 2,
        "children": 0,
        "estimated_arrival_time": "18:30",
        "special_requests": "Quiet corner room, feather-free hypoallergenic pillows",
        "guarantee_type": "Guaranteed",
        "early_checkin_requested": True,
        "late_checkout_requested": False,
        "guest": {
            "first_name": "Alexander",
            "last_name": "Pierce",
            "email": f"alex.pierce.{offset}@example.com",
            "phone": "+1-555-888-9999",
            "vip_tier": "Gold"
        }
    }

    res = client.post("/bookings", json=payload)
    assert res.status_code == 201
    booking = res.json()

    assert booking["adults"] == 2
    assert booking["children"] == 0
    assert booking["estimated_arrival_time"] == "18:30"
    assert "hypoallergenic pillows" in booking["special_requests"]
    assert booking["guarantee_type"] == "Guaranteed"
    assert booking["early_checkin_requested"] is True
    assert booking["late_checkout_requested"] is False

    # Verify retrieval via GET /bookings/{id}
    b_id = booking["id"]
    get_res = client.get(f"/bookings/{b_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["adults"] == 2
    assert fetched["estimated_arrival_time"] == "18:30"
    assert fetched["guarantee_type"] == "Guaranteed"
    assert fetched["room"]["id"] == 1


def test_max_occupancy_enforcement(client):
    """Verify that booking more guests than room max_occupancy is rejected with HTTP 422."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    offset = random.randint(460, 580)
    check_in = (date.today() + timedelta(days=offset)).isoformat()
    check_out = (date.today() + timedelta(days=offset + 2)).isoformat()

    # Room 101 max_occupancy is 2. Attempting to book 3 adults + 1 child (4 total) must fail.
    payload = {
        "room_id": 1,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": 3,
        "children": 1,
        "guest": {
            "first_name": "Overcrowded",
            "last_name": "Party",
            "email": f"overcrowded.{offset}@example.com",
            "phone": "+1-555-000-1111"
        }
    }

    res = client.post("/bookings", json=payload)
    assert res.status_code == 422
    err_msg = res.json()["detail"]
    assert "exceeds maximum room capacity" in err_msg


def test_auto_assign_room_algorithm(client):
    """Verify intelligent room auto-assignment engine scoring and candidate recommendation."""
    client.patch("/rooms/1/status", json={"status": "Available"})
    client.patch("/rooms/2/status", json={"status": "Available"})
    client.patch("/rooms/3/status", json={"status": "Available"})

    offset = random.randint(600, 750)
    check_in = (date.today() + timedelta(days=offset)).isoformat()
    check_out = (date.today() + timedelta(days=offset + 3)).isoformat()

    # Request auto-assignment for a Double room on Floor 2 for 2 adults
    req = {
        "check_in_date": check_in,
        "check_out_date": check_out,
        "room_type": "Double",
        "floor": 2,
        "adults": 2,
        "children": 0,
        "prefer_inspected": True
    }

    res = client.post("/bookings/auto-assign", json=req)
    assert res.status_code == 200
    data = res.json()

    assert data["assigned_room"] is not None
    assert data["assigned_room"]["room_type"] == "Double"
    assert data["assigned_room"]["floor"] == 2
    assert data["match_score"] >= 80
    assert len(data["criteria_applied"]) >= 3
    assert any("Floor preference" in c for c in data["criteria_applied"])


def test_auto_assign_no_available_rooms_scenario(client):
    """Verify auto-assign gracefully reports when party size exceeds all inventory."""
    check_in = (date.today() + timedelta(days=800)).isoformat()
    check_out = (date.today() + timedelta(days=802)).isoformat()

    # Request auto-assignment for 15 guests (exceeds all suites)
    req = {
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": 10,
        "children": 5
    }

    res = client.post("/bookings/auto-assign", json=req)
    assert res.status_code == 200
    data = res.json()

    assert data["assigned_room"] is None
    assert data["match_score"] == 0
    assert any("No eligible vacant room" in c for c in data["criteria_applied"])
