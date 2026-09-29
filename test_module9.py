"""
test_module9.py - Automated Test Suite for Module 9
Focus: Reservation Lifecycle & Checkout Engine (Check-In, Check-Out, Invoicing, Cancellation)
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from main import app


from database import get_db_connection


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_list_bookings_and_status_filtering(client):
    """Verify GET /bookings returns populated list with guest, room, and amenities."""
    response = client.get("/bookings")
    assert response.status_code == 200
    bookings = response.json()
    assert isinstance(bookings, list)
    assert len(bookings) > 0

    first = bookings[0]
    assert "id" in first
    assert "guest" in first
    assert "room" in first
    assert "amenities" in first
    assert "booking_status" in first

    # Test filtering by status
    conf_res = client.get("/bookings?status=Confirmed")
    assert conf_res.status_code == 200
    for b in conf_res.json():
        assert b["booking_status"] == "Confirmed"


def test_check_in_workflow_and_room_occupancy_transition(client):
    """Verify check-in transitions booking to 'Checked-in' and room to 'Occupied'."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=200)).isoformat()
        check_out = (date.today() + timedelta(days=202)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 1,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest": {
                "first_name": "Marcus",
                "last_name": "Vance",
                "email": "marcus.vance@example.com",
                "phone": "+1-555-0199"
            }
        })
        assert create_res.status_code == 201
        booking = create_res.json()
        booking_id = booking["id"]
        assert booking["booking_status"] == "Confirmed"

        # 2. Execute check-in
        check_in_res = client.post(f"/bookings/{booking_id}/check-in")
        assert check_in_res.status_code == 200
        updated_booking = check_in_res.json()
        assert updated_booking["booking_status"] == "Checked-in"

        # 3. Verify Room 1 is now Occupied
        room_res = client.get("/rooms")
        room_map = {r["id"]: r["status"] for r in room_res.json()}
        assert room_map[1] == "Occupied"

        # 4. Attempting duplicate check-in must fail with HTTP 400
        dup_res = client.post(f"/bookings/{booking_id}/check-in")
        assert dup_res.status_code == 400
        assert "cannot check in" in dup_res.json()["detail"].lower()
    finally:
        client.patch("/rooms/1/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM BookingAmenities WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_check_out_workflow_generates_invoice_and_flags_cleaning(client):
    """Verify checkout transitions to 'Checked-out', generates invoice folio, and marks room 'Cleaning'."""
    client.patch("/rooms/2/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=210)).isoformat()
        check_out = (date.today() + timedelta(days=213)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 2,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "amenity_ids": [1, 2],
            "guest": {
                "first_name": "Elena",
                "last_name": "Rostova",
                "email": "elena.rostova@example.com",
                "phone": "+1-555-0288"
            }
        })
        assert create_res.status_code == 201
        booking_id = create_res.json()["id"]

        # Check in first
        client.post(f"/bookings/{booking_id}/check-in")

        # 2. Execute checkout
        checkout_res = client.post(f"/bookings/{booking_id}/check-out")
        assert checkout_res.status_code == 200
        invoice = checkout_res.json()

        assert invoice["booking_id"] == booking_id
        assert invoice["status"] == "Checked-out"
        assert invoice["room_status_after_checkout"] == "Cleaning"
        assert invoice["nights"] == 3
        assert invoice["base_room_charge"] > 0
        assert invoice["amenities_charge"] > 0
        assert invoice["tax_amount"] > 0
        assert invoice["grand_total"] == round(invoice["base_room_charge"] + invoice["amenities_charge"] + invoice["tax_amount"], 2)
        assert len(invoice["invoice_breakdown"]) >= 3

        # 3. Room 2 must now be in 'Cleaning' status
        room_res = client.get("/rooms")
        room_map = {r["id"]: r["status"] for r in room_res.json()}
        assert room_map[2] == "Cleaning"

        # 4. Attempting to check out already checked-out booking fails with HTTP 400
        repeat_res = client.post(f"/bookings/{booking_id}/check-out")
        assert repeat_res.status_code == 400
    finally:
        client.patch("/rooms/2/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM BookingAmenities WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_cancellation_workflow_and_refund_policy(client):
    """Verify cancellation calculates refund policy and releases room back to catalog."""
    client.patch("/rooms/6/status", json={"status": "Available"})

    b_id = None
    try:
        future_in = (date.today() + timedelta(days=220)).isoformat()
        future_out = (date.today() + timedelta(days=223)).isoformat()
        b_res = client.post("/bookings", json={
            "room_id": 6,
            "check_in_date": future_in,
            "check_out_date": future_out,
            "guest": {
                "first_name": "David",
                "last_name": "Kim",
                "email": "david.kim@example.com",
                "phone": "+1-555-0377"
            }
        })
        assert b_res.status_code == 201
        b_id = b_res.json()["id"]
        total = b_res.json()["total_price"]

        # Cancel booking
        cancel_res = client.post(f"/bookings/{b_id}/cancel")
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()

        assert cancel_data["booking_id"] == b_id
        assert cancel_data["status"] == "Cancelled"
        assert cancel_data["refund_amount"] == total
        assert cancel_data["cancellation_fee"] == 0.0

        # Repeat cancellation fails with 400
        repeat_cancel = client.post(f"/bookings/{b_id}/cancel")
        assert repeat_cancel.status_code == 400
    finally:
        client.patch("/rooms/6/status", json={"status": "Available"})
        if b_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM BookingAmenities WHERE booking_id = ?;", (b_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (b_id,))
            conn.commit()
            conn.close()


def test_lifecycle_non_existent_booking_yields_404(client):
    """Verify that lifecycle mutations on non-existent IDs return HTTP 404."""
    assert client.post("/bookings/99999/check-in").status_code == 404
    assert client.post("/bookings/99999/check-out").status_code == 404
    assert client.post("/bookings/99999/cancel").status_code == 404
