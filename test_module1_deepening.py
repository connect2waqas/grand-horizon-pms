"""
test_module1_deepening.py - Automated Test Suite for Module 1 Deepening
Focus: Accommodations & Room Inventory Deepening (Floor hierarchy, max occupancy, bed configurations,
housekeeping inspection checklist, and room maintenance locking).
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db_connection


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_rooms_list_contains_architectural_fields(client):
    """Verify that GET /rooms returns deepened architectural fields for each accommodation."""
    response = client.get("/rooms")
    assert response.status_code == 200
    rooms = response.json()
    assert len(rooms) >= 6

    room = rooms[0]
    assert "floor" in room
    assert "max_occupancy" in room
    assert "bed_type" in room
    assert "view_type" in room
    assert "sq_meters" in room
    assert "is_smoking" in room
    assert "cleanliness_status" in room
    assert room["floor"] in [1, 2, 3]
    assert room["max_occupancy"] >= 1
    assert isinstance(room["sq_meters"], int)


def test_rooms_filtering_by_floor_and_occupancy(client):
    """Verify filtering inventory by floor and minimum occupancy."""
    # Filter for floor 2
    r_floor2 = client.get("/rooms?floor=2")
    assert r_floor2.status_code == 200
    f2_rooms = r_floor2.json()
    assert len(f2_rooms) >= 1
    for rm in f2_rooms:
        assert rm["floor"] == 2

    # Filter for min_occupancy 4
    r_occ4 = client.get("/rooms?min_occupancy=4")
    assert r_occ4.status_code == 200
    occ4_rooms = r_occ4.json()
    assert len(occ4_rooms) >= 1
    for rm in occ4_rooms:
        assert rm["max_occupancy"] >= 4


def test_room_specifications_endpoint(client):
    """Verify GET /rooms/{room_id}/specifications returns comprehensive architectural spec."""
    response = client.get("/rooms/1/specifications")
    assert response.status_code == 200
    spec = response.json()

    assert spec["id"] == 1
    assert "room_number" in spec
    assert "floor" in spec
    assert "max_occupancy" in spec
    assert "bed_type" in spec
    assert "view_type" in spec
    assert "sq_meters" in spec
    assert "is_smoking" in spec
    assert "cleanliness_status" in spec
    assert "active_booking_id" in spec
    assert "last_cleaned_at" in spec


def test_housekeeping_inspection_workflow_and_audit(client):
    """Verify housekeeping state mutations, auto-operational release, and audit logs."""
    room_id = 1
    # 1. Inspect room to Dirty -> Should automatically transition operational status to Cleaning
    res_dirty = client.patch(f"/rooms/{room_id}/housekeeping", json={
        "cleanliness_status": "Dirty",
        "inspected_by": "Maria Gonzales (Head Housekeeper)",
        "notes": "Post checkout full linen replacement required"
    })
    assert res_dirty.status_code == 200
    dirty_data = res_dirty.json()
    assert dirty_data["cleanliness_status"] == "Dirty"
    assert dirty_data["status"] == "Cleaning"

    # 2. Inspect room to Inspected -> Should auto-release operational status to Available
    res_inspected = client.patch(f"/rooms/{room_id}/housekeeping", json={
        "cleanliness_status": "Inspected",
        "inspected_by": "Maria Gonzales (Head Housekeeper)",
        "notes": "Turnover complete, all high-touch surfaces disinfected"
    })
    assert res_inspected.status_code == 200
    inspected_data = res_inspected.json()
    assert inspected_data["cleanliness_status"] == "Inspected"
    assert inspected_data["status"] == "Available"

    # 3. Check audit logs for HOUSEKEEPING_INSPECTED event
    audit_res = client.get("/audit-logs?entity_type=Room&action=HOUSEKEEPING_INSPECTED")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["action"] == "HOUSEKEEPING_INSPECTED"
    details = latest["details"]
    if isinstance(details, str):
        import json
        details = json.loads(details)
    assert details["new_cleanliness"] == "Inspected"
    assert details["inspected_by"] == "Maria Gonzales (Head Housekeeper)"


def test_room_maintenance_locking_and_release(client):
    """Verify locking a room under maintenance with a mandatory reason, and releasing it."""
    room_id = 2
    # Lock for maintenance
    lock_res = client.patch(f"/rooms/{room_id}/status", json={
        "status": "Maintenance",
        "lock_reason": "HVAC compressor servicing and acoustic check"
    })
    assert lock_res.status_code == 200
    locked_data = lock_res.json()
    assert locked_data["status"] == "Maintenance"
    assert locked_data["lock_reason"] == "HVAC compressor servicing and acoustic check"

    # Verify specs reflect lock_reason
    spec_res = client.get(f"/rooms/{room_id}/specifications")
    assert spec_res.status_code == 200
    assert spec_res.json()["lock_reason"] == "HVAC compressor servicing and acoustic check"

    # Release room back to Available
    release_res = client.patch(f"/rooms/{room_id}/status", json={
        "status": "Available"
    })
    assert release_res.status_code == 200
    released_data = release_res.json()
    assert released_data["status"] == "Available"
    assert released_data["lock_reason"] is None
