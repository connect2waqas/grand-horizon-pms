"""
test_module4_deepening.py - Module 4: Housekeeping & Room Status Management
Comprehensive unit and integration test suite covering:
1. Housekeeping dashboard KPI aggregations (Inspected, Clean, Dirty, DND, Tasks)
2. Turnover task catalog listing and query parameter filtering
3. Dispatching new housekeeping tasks (Checkout Turnover, Stayover, Deep Clean)
4. Task lifecycle state progression: Pending -> In Progress -> Cleaned -> Inspected
5. Inspection quality gates: Auto-releasing rooms from 'Cleaning' to 'Available' upon passing audit
6. Checklist tracking: Linen, amenities, sanitation booleans
7. Room attendant assignment, priority escalation, and Do Not Disturb (DND) toggle
8. Automatic turnover task creation upon guest check-out
"""

import os
import sqlite3
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from main import app
from database import get_db_connection, init_db, seed_rooms, seed_housekeeping_tasks
from schemas import (
    CleanlinessStatus,
    HousekeepingPriority,
    HousekeepingTaskStatus,
    HousekeepingTaskType,
    RoomStatus,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database schema is fresh and seeded for each test."""
    init_db()
    seed_rooms()
    seed_housekeeping_tasks()
    yield


def test_housekeeping_dashboard_kpis():
    """Verify executive housekeeping dashboard summary endpoint returns valid operational metrics."""
    response = client.get("/api/housekeeping/dashboard")
    assert response.status_code == 200
    data = response.json()

    assert "total_rooms" in data
    assert "inspected_ready" in data
    assert "clean_pending_inspection" in data
    assert "dirty_needs_turnover" in data
    assert "cleaning_in_progress" in data
    assert "touch_up_required" in data
    assert "dnd_active" in data
    assert "urgent_priority_count" in data
    assert "pending_tasks_count" in data
    assert "active_housekeepers" in data
    assert isinstance(data["active_housekeepers"], list)
    assert data["total_rooms"] >= 6


def test_housekeeping_tasks_listing_and_filtering():
    """Verify listing housekeeping tasks and filtering by priority, status, and room."""
    # List all
    res = client.get("/api/housekeeping/tasks")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) >= 3

    # Filter by priority
    res_priority = client.get("/api/housekeeping/tasks?priority=Rush+Checkout+Turnover")
    assert res_priority.status_code == 200
    rush_tasks = res_priority.json()
    for t in rush_tasks:
        assert t["priority"] == "Rush Checkout Turnover"


def test_housekeeping_task_dispatch_and_room_sync():
    """Verify dispatching a new housekeeping assignment and verifying room attendant sync."""
    dispatch_payload = {
        "room_id": 2,
        "task_type": "Deep Clean",
        "priority": "Urgent VIP Arrival",
        "assigned_housekeeper": "Elena Rostova",
        "notes": "VIP arrival expected at 4 PM. Extra amenities and luxury bathrobes required.",
    }
    res = client.post("/api/housekeeping/tasks", json=dispatch_payload)
    assert res.status_code == 201
    task = res.json()

    assert task["room_id"] == 2
    assert task["task_type"] == "Deep Clean"
    assert task["priority"] == "Urgent VIP Arrival"
    assert task["assigned_housekeeper"] == "Elena Rostova"
    assert task["status"] == "Pending"
    assert task["room_number"] is not None

    # Verify room was updated with the attendant and priority
    room_res = client.get("/api/rooms")
    assert room_res.status_code == 200
    room2 = next(r for r in room_res.json() if r["id"] == 2)
    assert room2["assigned_housekeeper"] == "Elena Rostova"
    assert room2["cleaning_priority"] == "Urgent VIP Arrival"


def test_housekeeping_task_lifecycle_and_auto_release():
    """
    Test full lifecycle workflow:
    Pending -> In Progress (marks room Cleaning) -> Cleaned -> Inspected (releases room to Available)
    """
    # 1. Create a task for Room 5 (set room to Cleaning first)
    client.patch("/api/rooms/5/status", json={"status": "Cleaning"})
    client.patch("/api/rooms/5/housekeeping", json={"cleanliness_status": "Dirty"})

    dispatch_res = client.post("/api/housekeeping/tasks", json={
        "room_id": 5,
        "task_type": "Checkout Turnover",
        "priority": "High",
        "assigned_housekeeper": "David Kim",
        "notes": "Sanitize and remake beds.",
    })
    task_id = dispatch_res.json()["id"]

    # 2. Start Task -> In Progress
    progress_res = client.patch(f"/api/housekeeping/tasks/{task_id}", json={
        "status": "In Progress"
    })
    assert progress_res.status_code == 200
    assert progress_res.json()["status"] == "In Progress"
    assert progress_res.json()["started_at"] is not None

    # 3. Complete Checklist and mark Cleaned
    cleaned_res = client.patch(f"/api/housekeeping/tasks/{task_id}", json={
        "status": "Cleaned",
        "linen_changed": True,
        "amenities_restocked": True,
        "bathroom_sanitized": True,
        "notes": "All linens replaced, minibar fully stocked.",
    })
    assert cleaned_res.status_code == 200
    assert cleaned_res.json()["status"] == "Cleaned"
    assert cleaned_res.json()["linen_changed"] is True
    assert cleaned_res.json()["completed_at"] is not None

    # Verify Room is now marked Clean
    room_res = client.get("/api/rooms")
    room5 = next(r for r in room_res.json() if r["id"] == 5)
    assert room5["cleanliness_status"] == "Clean"

    # 4. Executive Housekeeper passes inspection -> Inspected
    inspect_res = client.patch(f"/api/housekeeping/tasks/{task_id}", json={
        "status": "Inspected",
        "inspected_by": "Head Inspector Sarah Vance",
        "inspector_notes": "Spotless condition. Passed 5-star audit standards.",
    })
    assert inspect_res.status_code == 200
    task_final = inspect_res.json()
    assert task_final["status"] == "Inspected"
    assert task_final["inspected_by"] == "Head Inspector Sarah Vance"
    assert task_final["inspected_at"] is not None

    # 5. Check Room 5 is AUTO-RELEASED back to 'Available' and 'Inspected'!
    room_res_after = client.get("/api/rooms")
    room5_after = next(r for r in room_res_after.json() if r["id"] == 5)
    assert room5_after["cleanliness_status"] == "Inspected"
    assert room5_after["status"] == "Available"
    assert room5_after["last_inspected_at"] is not None


def test_room_dnd_and_housekeeping_update():
    """Verify updating room housekeeping attributes: DND toggle, attendant, priority."""
    res = client.patch("/api/rooms/1/housekeeping", json={
        "cleanliness_status": "Clean",
        "assigned_housekeeper": "Carlos Gomez",
        "cleaning_priority": "High",
        "dnd_status": True,
        "notes": "Guest requested Do Not Disturb until 2 PM.",
    })
    assert res.status_code == 200
    updated_room = res.json()
    assert updated_room["assigned_housekeeper"] == "Carlos Gomez"
    assert updated_room["cleaning_priority"] == "High"
    assert updated_room["dnd_status"] is True

    # Check dashboard reflects active DND count
    dash_res = client.get("/api/housekeeping/dashboard")
    assert dash_res.json()["dnd_active"] >= 1


def test_checkout_auto_dispatches_housekeeping_task():
    """Verify that checking out a reservation automatically creates a Checkout Turnover task."""
    # 1. Clear any conflicting bookings for room 6 and set to Available
    conn = get_db_connection()
    conn.execute("DELETE FROM Bookings WHERE room_id = 6;")
    conn.commit()
    conn.close()

    client.patch("/api/rooms/6/status", json={"status": "Available"})
    check_in = (date.today() + timedelta(days=280)).isoformat()
    check_out = (date.today() + timedelta(days=282)).isoformat()
    booking_res = client.post("/api/bookings", json={
        "guest_id": 1,
        "room_id": 6,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "notes": "Turnover automation test",
    })
    assert booking_res.status_code == 201
    booking_id = booking_res.json()["id"]

    # 2. Check in guest first
    ci_res = client.post(f"/api/bookings/{booking_id}/check-in")
    assert ci_res.status_code == 200

    # 3. Check out booking
    co_res = client.post(f"/api/bookings/{booking_id}/check-out")
    assert co_res.status_code == 200

    # 3. Verify room operational state is 'Cleaning' and 'Dirty'
    room_res = client.get("/api/rooms")
    room6 = next(r for r in room_res.json() if r["id"] == 6)
    assert room6["status"] == "Cleaning"
    assert room6["cleanliness_status"] == "Dirty"

    # 4. Verify a new HousekeepingTask was auto-dispatched for Room 6
    tasks_res = client.get("/api/housekeeping/tasks?room_id=6")
    assert tasks_res.status_code == 200
    room6_tasks = tasks_res.json()
    assert len(room6_tasks) >= 1
    latest_task = room6_tasks[0]
    assert latest_task["task_type"] == "Checkout Turnover"
    assert latest_task["priority"] == "Rush Checkout Turnover"
    assert latest_task["status"] == "Pending"
