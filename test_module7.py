"""
test_module7.py - Automated Test Suite for Module 7
Focus: Dynamic Housekeeping & Room Status Mutation (PATCH /rooms/{room_id}/status)
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_update_room_status_to_cleaning(client):
    """Verify that an available room can be transitioned to Cleaning."""
    response = client.patch(
        "/rooms/1/status",
        json={"status": "Cleaning"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["status"] == "Cleaning"

    # Verify persistent state via GET /rooms
    get_res = client.get("/rooms")
    assert get_res.status_code == 200
    rooms = {r["id"]: r["status"] for r in get_res.json()}
    assert rooms[1] == "Cleaning"


def test_update_room_status_to_available(client):
    """Verify that a cleaned room can be marked Available for reservations."""
    response = client.patch(
        "/rooms/1/status",
        json={"status": "Available"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["status"] == "Available"


def test_update_room_status_to_maintenance(client):
    """Verify that an operational room can be marked as Maintenance."""
    response = client.patch(
        "/rooms/2/status",
        json={"status": "Maintenance"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["status"] == "Maintenance"

    # Default GET /rooms excludes Maintenance rooms
    get_res = client.get("/rooms")
    assert get_res.status_code == 200
    room_ids = [r["id"] for r in get_res.json()]
    assert 2 not in room_ids

    # Query with include_maintenance=true includes it
    get_maint_res = client.get("/rooms?include_maintenance=true")
    assert get_maint_res.status_code == 200
    maint_room_ids = [r["id"] for r in get_maint_res.json()]
    assert 2 in maint_room_ids

    # Revert room 2 back to Available to preserve state
    client.patch("/rooms/2/status", json={"status": "Available"})


def test_update_room_status_not_found(client):
    """Verify that non-existent room ID yields HTTP 404."""
    response = client.patch(
        "/rooms/9999/status",
        json={"status": "Cleaning"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_room_status_invalid_enum(client):
    """Verify that invalid status string yields HTTP 422 Unprocessable Entity."""
    response = client.patch(
        "/rooms/1/status",
        json={"status": "UnderConstruction"},
    )
    assert response.status_code == 422


def test_include_maintenance_query_parameter(client):
    """Verify that include_maintenance flag properly controls visibility of maintenance rooms."""
    # Set room 2 to Maintenance
    client.patch("/rooms/2/status", json={"status": "Maintenance"})

    # Without flag: Room 2 is excluded
    res_default = client.get("/rooms")
    assert res_default.status_code == 200
    room_ids_default = [r["id"] for r in res_default.json()]
    assert 2 not in room_ids_default

    # With flag: Room 2 is included
    res_maint = client.get("/rooms?include_maintenance=true")
    assert res_maint.status_code == 200
    room_ids_maint = [r["id"] for r in res_maint.json()]
    assert 2 in room_ids_maint

    # Cleanup: revert back to Available
    client.patch("/rooms/2/status", json={"status": "Available"})
