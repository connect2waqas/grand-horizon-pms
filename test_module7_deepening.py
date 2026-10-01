"""
test_module7_deepening.py - Comprehensive Automated Test Battery for Module 7
Focus: Advanced Room Operations, Out-of-Order (OOO) Management & Guest Relocation Engine
"""

import random
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db_connection, init_db, seed_rooms, seed_amenities, seed_room_operations


@pytest.fixture(autouse=True)
def reset_db():
    """Ensure clean database state before each test execution."""
    init_db()
    seed_rooms()
    seed_amenities()
    seed_room_operations()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE RoomLockouts SET is_active = 0 WHERE id > 1;")
    cursor.execute("UPDATE Rooms SET lock_reason = NULL WHERE id NOT IN (SELECT room_id FROM RoomLockouts WHERE is_active = 1);")
    conn.commit()
    conn.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_declare_room_lockout_success(client):
    """Verify taking an available room out of order creates lockout and updates room status."""
    # Ensure Room 2 is in clean Available status
    client.patch("/api/rooms/2/status", json={"status": "Available"})

    payload = {
        "lockout_type": "Out_of_Order",
        "reason": "Air conditioner cooling coil freezing up",
        "assigned_trade": "HVAC Mechanicals",
        "expected_completion": "2026-10-05T18:00:00Z",
        "authorized_by": "Senior Facilities Director",
        "notes": "Refrigerant line leak detected in secondary plenum",
    }
    res = client.post("/api/rooms/2/lockout", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["room_id"] == 2
    assert data["room_number"] == "102"
    assert data["lockout_type"] == "Out_of_Order"
    assert data["reason"] == payload["reason"]
    assert data["is_active"] is True

    # Verify room status is Maintenance and has lock_reason
    room_res = client.get("/api/rooms?include_maintenance=true")
    assert room_res.status_code == 200
    r2 = next(r for r in room_res.json() if r["id"] == 2)
    assert r2["status"] == "Maintenance"
    assert r2["lock_reason"] == payload["reason"]


def test_lockout_rejected_for_occupied_room(client):
    """Verify that taking an actively occupied room out of order is rejected with HTTP 400."""
    # First set Room 1 to Occupied
    client.patch("/api/rooms/1/status", json={"status": "Occupied"})

    payload = {
        "lockout_type": "Out_of_Order",
        "reason": "Sudden plumbing fixture burst",
        "authorized_by": "Duty Manager",
    }
    res = client.post("/api/rooms/1/lockout", json=payload)
    assert res.status_code == 400
    assert "currently occupied" in res.json()["detail"].lower()


def test_release_room_lockout(client):
    """Verify resolving repairs releases room from OOO back to Cleaning for turnover."""
    # Ensure Room 3 is Available
    client.patch("/api/rooms/3/status", json={"status": "Available"})

    # Declare lockout on room 3
    client.post("/api/rooms/3/lockout", json={
        "lockout_type": "Out_of_Service",
        "reason": "Deep carpet steam cleaning and ozone deodorization",
        "authorized_by": "Housekeeping Executive",
    })

    # Release lockout
    release_payload = {
        "released_by": "Lead Turnover Inspector",
        "target_cleanliness": "Touch-up Required",
        "resolution_notes": "Carpet completely dry; ozone cycle completed.",
    }
    res = client.post("/api/rooms/3/release", json=release_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_active"] is False
    assert data["resolved_by"] == "Lead Turnover Inspector"
    assert data["resolution_notes"] == release_payload["resolution_notes"]

    # Verify Room 3 is now Cleaning and available for turnover
    room_res = client.get("/api/rooms?include_maintenance=true")
    r3 = next(r for r in room_res.json() if r["id"] == 3)
    assert r3["status"] == "Cleaning"
    assert r3["lock_reason"] is None


def test_emergency_guest_room_move_success(client):
    """Verify emergency room relocation transfers reservation, updates room states, and re-encodes keycards."""
    # Ensure Room 1 is Available and Room 3 is Available
    client.patch("/api/rooms/1/status", json={"status": "Available"})
    client.patch("/api/rooms/3/status", json={"status": "Available"})

    offset = random.randint(140000, 170000)
    ci = (date.today() + timedelta(days=offset)).isoformat()
    co = (date.today() + timedelta(days=offset + 4)).isoformat()

    # 1. Create a reservation for Room 1
    booking_payload = {
        "room_id": 1,
        "guest": {
            "first_name": "Marcus",
            "last_name": "Vance",
            "email": f"marcus.vance.{offset}@grandhorizon.com",
            "phone": "+1-555-0199",
        },
        "check_in_date": ci,
        "check_out_date": co,
        "adults": 2,
    }
    b_res = client.post("/api/bookings", json=booking_payload)
    assert b_res.status_code == 201
    booking_id = b_res.json()["id"]

    # 2. Check in the booking
    cin_res = client.post(f"/api/bookings/{booking_id}/check-in")
    assert cin_res.status_code == 200

    # Issue an RFID keycard for Room 1
    unique_uid = f"MOVE-RFID-{random.randint(10000, 99999)}"
    kc_res = client.post("/api/keycards/issue", json={
        "room_id": 1,
        "booking_id": booking_id,
        "holder_name": "Marcus Vance",
        "card_type": "Guest",
        "card_uid": unique_uid,
    })
    assert kc_res.status_code == 201

    # 3. Execute emergency room move to Room 3 (which is Available)
    move_payload = {
        "new_room_id": 3,
        "reason": "Water pressure loss in primary shower fixture",
        "relocated_by": "Night Duty Manager",
        "transfer_keycards": True,
        "old_room_lockout": True,
    }
    move_res = client.post(f"/api/bookings/{booking_id}/room-move", json=move_payload)
    assert move_res.status_code == 200
    move_data = move_res.json()
    assert move_data["booking_id"] == booking_id
    assert move_data["old_room_number"] == "101"
    assert move_data["new_room_number"] == "201"
    assert move_data["old_room_new_status"] == "Maintenance"
    assert move_data["new_room_status"] == "Occupied"

    # Verify booking now points to Room 3
    b_get = client.get(f"/api/bookings/{booking_id}")
    assert b_get.status_code == 200
    assert b_get.json()["room_id"] == 3

    # Verify old room is locked out in Maintenance
    all_rooms = client.get("/api/rooms?include_maintenance=true").json()
    old_room = next(r for r in all_rooms if r["id"] == 1)
    new_room = next(r for r in all_rooms if r["id"] == 3)
    assert old_room["status"] == "Maintenance"
    assert "Vacated on guest room move" in old_room["lock_reason"]
    assert new_room["status"] == "Occupied"

    # Verify keycard was re-assigned to Room 3
    kcs = client.get(f"/api/keycards?booking_id={booking_id}").json()
    assert len(kcs) >= 1
    assert any(k["card_uid"] == unique_uid and k["room_id"] == 3 for k in kcs)


def test_room_move_rejected_if_destination_occupied_or_invalid(client):
    """Verify that moving a guest to an already occupied room yields HTTP 409."""
    # Set Room 1 to Available, Room 2 to Occupied
    client.patch("/api/rooms/1/status", json={"status": "Available"})
    client.patch("/api/rooms/2/status", json={"status": "Occupied"})

    offset = random.randint(180000, 210000)
    ci = (date.today() + timedelta(days=offset)).isoformat()
    co = (date.today() + timedelta(days=offset + 2)).isoformat()

    # Create & check in booking for Room 1
    b_res = client.post("/api/bookings", json={
        "room_id": 1,
        "guest": {
            "first_name": "Elena",
            "last_name": "Rostova",
            "email": f"elena.rostova.{offset}@grandhorizon.com",
            "phone": "+1-555-0822",
        },
        "check_in_date": ci,
        "check_out_date": co,
    })
    assert b_res.status_code == 201
    booking_id = b_res.json()["id"]
    client.post(f"/api/bookings/{booking_id}/check-in")

    # Try moving to Room 2 (Occupied) -> 409
    res_conflict = client.post(f"/api/bookings/{booking_id}/room-move", json={
        "new_room_id": 2,
        "reason": "Guest request",
    })
    assert res_conflict.status_code == 409

    # Try moving to the same room (Room 1) -> 400
    res_same = client.post(f"/api/bookings/{booking_id}/room-move", json={
        "new_room_id": 1,
        "reason": "No-op move",
    })
    assert res_same.status_code == 400


def test_room_operations_dashboard_and_moves_history(client):
    """Verify room operations consolidated metrics and relocation audit history."""
    dash_res = client.get("/api/rooms/operations-dashboard")
    assert dash_res.status_code == 200
    data = dash_res.json()
    assert "total_rooms" in data
    assert "available_count" in data
    assert "occupied_count" in data
    assert "active_lockouts" in data
    assert "recent_room_moves" in data
    assert isinstance(data["active_lockouts"], list)
    assert isinstance(data["recent_room_moves"], list)

