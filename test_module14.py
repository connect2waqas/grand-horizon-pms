"""
test_module14.py - Automated Test Suite for Module 14
Focus: Guest Folio & Incidentals Billing Engine (Room Charges, POS Presets, Void Auditing, Checkout Folio)
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


def test_get_folio_catalog(client):
    """Verify GET /folio-charges/categories returns supported categories and item presets."""
    response = client.get("/folio-charges/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "presets" in data
    assert "Dining" in data["categories"]
    assert "Minibar" in data["categories"]
    assert "Spa" in data["categories"]
    assert "Parking" in data["categories"]
    assert len(data["presets"]["Dining"]) >= 1


def test_post_incidental_charge_and_get_folio(client):
    """Verify posting incidental charges updates the folio statement and balance due."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=230)).isoformat()
        check_out = (date.today() + timedelta(days=232)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 1,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest": {
                "first_name": "Julian",
                "last_name": "Sterling",
                "email": "julian.sterling@example.com",
                "phone": "+1-555-0311",
            }
        })
        assert create_res.status_code == 201
        booking_id = create_res.json()["id"]

        # Post Dining charge
        charge1_res = client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Dining",
            "description": "Executive Wagyu Burger & Truffle Fries",
            "unit_price": 38.50,
            "quantity": 1,
            "posted_by": "Room Service Chef",
        })
        assert charge1_res.status_code == 201
        c1 = charge1_res.json()
        assert c1["booking_id"] == booking_id
        assert c1["total_price"] == 38.50
        assert c1["status"] == "Billed"

        # Post Minibar charge (quantity 2)
        charge2_res = client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Minibar",
            "description": "Sparkling Italian Mineral Water",
            "unit_price": 8.00,
            "quantity": 2,
            "posted_by": "Minibar Attendant",
        })
        assert charge2_res.status_code == 201
        c2 = charge2_res.json()
        assert c2["total_price"] == 16.00

        # Retrieve guest folio statement
        folio_res = client.get(f"/bookings/{booking_id}/folio")
        assert folio_res.status_code == 200
        folio = folio_res.json()

        assert folio["booking_id"] == booking_id
        assert folio["guest_name"] == "Julian Sterling"
        assert folio["incidentals_total"] == round(38.50 + 16.00, 2)
        assert folio["grand_total"] == round(folio["room_base_charge"] + folio["amenities_charge"] + 54.50, 2)
        assert folio["balance_due"] == folio["grand_total"]
        assert len(folio["incidentals"]) == 2
    finally:
        client.patch("/rooms/1/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM FolioCharges WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM BookingAmenities WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_void_incidental_charge_recalculates_balance(client):
    """Verify voiding a charge marks it Voided with reason and excludes it from incidentals total."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=240)).isoformat()
        check_out = (date.today() + timedelta(days=242)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 1,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest": {
                "first_name": "Serena",
                "last_name": "Kowalski",
                "email": "serena.k@example.com",
                "phone": "+1-555-0322",
            }
        })
        assert create_res.status_code == 201
        booking_id = create_res.json()["id"]

        # Post two charges
        c1 = client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Spa",
            "description": "Deep Tissue Massage",
            "unit_price": 120.00,
            "quantity": 1,
        }).json()

        c2 = client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Dining",
            "description": "Erroneous Mini Bar Posting",
            "unit_price": 45.00,
            "quantity": 1,
        }).json()

        # Void charge 2
        void_res = client.post(f"/folio-charges/{c2['id']}/void", json={
            "void_reason": "Guest did not consume minibar items; clerical error."
        })
        assert void_res.status_code == 200
        voided = void_res.json()
        assert voided["status"] == "Voided"
        assert voided["void_reason"] == "Guest did not consume minibar items; clerical error."

        # Fetch folio and verify active incidentals total only reflects c1
        folio = client.get(f"/bookings/{booking_id}/folio").json()
        assert folio["incidentals_total"] == 120.00
        assert len(folio["incidentals"]) == 2

        # Second void attempt on same charge must return 400
        dup_void = client.post(f"/folio-charges/{c2['id']}/void", json={
            "void_reason": "Another attempt to void"
        })
        assert dup_void.status_code == 400
        assert "already been voided" in dup_void.json()["detail"].lower()
    finally:
        client.patch("/rooms/1/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM FolioCharges WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_post_charge_to_cancelled_booking_fails(client):
    """Verify attempting to post an incidental to a cancelled reservation fails with 400."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=250)).isoformat()
        check_out = (date.today() + timedelta(days=252)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 1,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest": {
                "first_name": "Devon",
                "last_name": "Archer",
                "email": "devon.archer@example.com",
                "phone": "+1-555-0333",
            }
        })
        booking_id = create_res.json()["id"]

        # Cancel reservation
        cancel_res = client.post(f"/bookings/{booking_id}/cancel")
        assert cancel_res.status_code == 200

        # Attempt to post charge
        charge_res = client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Dining",
            "description": "Late Room Service",
            "unit_price": 25.00,
            "quantity": 1,
        })
        assert charge_res.status_code == 400
        assert "cannot post incidental charges" in charge_res.json()["detail"].lower()
    finally:
        client.patch("/rooms/1/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM FolioCharges WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_checkout_invoice_includes_folio_incidentals(client):
    """Verify checking out a reservation rolls non-voided incidentals into final invoice and marks them Paid."""
    client.patch("/rooms/2/status", json={"status": "Available"})

    booking_id = None
    try:
        check_in = (date.today() + timedelta(days=260)).isoformat()
        check_out = (date.today() + timedelta(days=262)).isoformat()
        create_res = client.post("/bookings", json={
            "room_id": 2,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest": {
                "first_name": "Natasha",
                "last_name": "Roman",
                "email": "natasha.roman@example.com",
                "phone": "+1-555-0344",
            }
        })
        booking_id = create_res.json()["id"]

        # Check in
        client.post(f"/bookings/{booking_id}/check-in")

        # Post Valet Parking charge
        client.post(f"/bookings/{booking_id}/charges", json={
            "service_category": "Parking",
            "description": "Overnight Valet Parking",
            "unit_price": 25.00,
            "quantity": 2,
        })

        # Process departure checkout
        checkout_res = client.post(f"/bookings/{booking_id}/check-out")
        assert checkout_res.status_code == 200
        invoice = checkout_res.json()

        assert invoice["booking_id"] == booking_id
        assert invoice["status"] == "Checked-out"
        assert invoice["incidentals_charge"] == 50.00

        # Check invoice breakdown line items include the incidental
        descriptions = [item["description"] for item in invoice["invoice_breakdown"]]
        assert any("Overnight Valet Parking" in d for d in descriptions)

        # Verify database record is marked 'Paid'
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM FolioCharges WHERE booking_id = ?;", (booking_id,))
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "Paid"
        conn.close()
    finally:
        client.patch("/rooms/2/status", json={"status": "Available"})
        if booking_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM FolioCharges WHERE booking_id = ?;", (booking_id,))
            conn.execute("DELETE FROM Bookings WHERE id = ?;", (booking_id,))
            conn.commit()
            conn.close()


def test_invalid_booking_or_charge_yields_404(client):
    """Verify appropriate 404 responses for non-existent reservations or folio charges."""
    res1 = client.get("/bookings/999999/folio")
    assert res1.status_code == 404

    res2 = client.post("/bookings/999999/charges", json={
        "service_category": "Dining",
        "description": "Ghost Order",
        "unit_price": 10.0,
        "quantity": 1,
    })
    assert res2.status_code == 404

    res3 = client.post("/folio-charges/999999/void", json={
        "void_reason": "Non-existent charge",
    })
    assert res3.status_code == 404
