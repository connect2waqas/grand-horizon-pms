"""
test_module5_deepening.py - Automated Test Suite for Module 5 Deepening
Focus: Room Keycard / Access Control & Security Logging
- RFID / NFC Keycard Credential Lifecycle (Issuance, Encoding, Revocation)
- Physical Door Lock Tap Simulator & Multi-Tier Permission Verification (Guest, Master, Housekeeping, Maintenance)
- Access Logs Security Audit Trail & Intrusion Attempt Tracking
- Automatic Credential Encoding on Check-In & Instant Deactivation on Departure Check-Out
- Security KPI Dashboard Aggregation
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


def test_access_control_dashboard_kpis(client):
    """Verify GET /api/access-control/dashboard returns complete security KPI metrics."""
    res = client.get("/api/access-control/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert "total_active_cards" in data
    assert "guest_cards_active" in data
    assert "staff_master_cards" in data
    assert "revoked_cards_count" in data
    assert "total_access_taps_today" in data
    assert "granted_taps_today" in data
    assert "denied_intrusions_today" in data
    assert "recent_denied_events" in data

    assert data["total_active_cards"] >= 2
    assert data["staff_master_cards"] >= 1
    assert isinstance(data["recent_denied_events"], list)


def test_keycards_listing_and_filtering(client):
    """Verify GET /api/keycards returns catalog with multi-field filtering."""
    # List all
    res = client.get("/api/keycards")
    assert res.status_code == 200
    cards = res.json()
    assert len(cards) >= 3

    # Filter by status=Active
    res_active = client.get("/api/keycards?status=Active")
    assert res_active.status_code == 200
    for c in res_active.json():
        assert c["status"] == "Active"

    # Filter by card_type=Staff Master
    res_master = client.get("/api/keycards?card_type=Staff%20Master")
    assert res_master.status_code == 200
    for c in res_master.json():
        assert c["card_type"] == "Staff Master"

    # Search filter
    res_search = client.get("/api/keycards?search=Alexander")
    assert res_search.status_code == 200
    assert any("Alexander" in c["holder_name"] for c in res_search.json())


def test_issue_and_revoke_keycard_lifecycle(client):
    """Verify issuing a new keycard, tapping a door lock, and revoking the credential."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    unique_uid = f"TEST-RFID-{random.randint(100000, 999999)}"
    issue_payload = {
        "room_id": 1,
        "holder_name": "VIP Marcus Aurelius",
        "card_type": "Guest",
        "card_uid": unique_uid,
        "issued_by": "Senior Front Desk Lead",
        "notes": "VIP arrival executive keycard",
    }

    # 1. Issue Keycard
    res = client.post("/api/keycards/issue", json=issue_payload)
    assert res.status_code == 201
    card = res.json()
    assert card["card_uid"] == unique_uid
    assert card["room_id"] == 1
    assert card["status"] == "Active"
    card_id = card["id"]

    # 2. Door Tap: Should be Granted for Room 1
    tap_req = {
        "card_uid": unique_uid,
        "room_id": 1,
        "reader_location": "Room 101 Main Door",
    }
    tap_res = client.post("/api/access-control/tap", json=tap_req)
    assert tap_res.status_code == 200
    tap_data = tap_res.json()
    assert tap_data["access_granted"] is True
    assert tap_data["event_type"] == "Granted"
    assert "Welcome" in tap_data["message"]

    # 3. Revoke Keycard
    revoke_req = {
        "reason": "Card reported lost by guest during breakfast",
        "revoked_by": "Duty Security Officer",
    }
    rev_res = client.post(f"/api/keycards/{card_id}/revoke", json=revoke_req)
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["status"] == "Revoked"
    assert rev_data["revoked_reason"] == "Card reported lost by guest during breakfast"
    assert rev_data["revoked_at"] is not None

    # 4. Door Tap with revoked card: Should be Denied - Card Revoked
    tap_res2 = client.post("/api/access-control/tap", json=tap_req)
    assert tap_res2.status_code == 200
    tap_data2 = tap_res2.json()
    assert tap_data2["access_granted"] is False
    assert tap_data2["event_type"] == "Denied - Card Revoked"
    assert "revoked" in tap_data2["message"].lower()


def test_door_tap_permissions_and_lockouts(client):
    """Verify multi-tier permissions, room mismatch denials, and maintenance lockouts."""
    # Ensure Room 1 & 2 available
    client.patch("/rooms/1/status", json={"status": "Available"})
    client.patch("/rooms/2/status", json={"status": "Available"})

    # Issue Guest card for Room 1
    guest_uid = f"GUEST-PERM-{random.randint(10000, 99999)}"
    client.post("/api/keycards/issue", json={
        "room_id": 1,
        "holder_name": "Room One Guest",
        "card_type": "Guest",
        "card_uid": guest_uid,
    })

    # Issue Staff Master card (universal access)
    master_uid = f"MASTER-PERM-{random.randint(10000, 99999)}"
    client.post("/api/keycards/issue", json={
        "room_id": None,
        "holder_name": "Operations Director",
        "card_type": "Staff Master",
        "card_uid": master_uid,
    })

    # 1. Guest card taps Room 2 -> Denied - Invalid Room
    r_mismatch = client.post("/api/access-control/tap", json={
        "card_uid": guest_uid,
        "room_id": 2,
    })
    assert r_mismatch.status_code == 200
    assert r_mismatch.json()["access_granted"] is False
    assert r_mismatch.json()["event_type"] == "Denied - Invalid Room"

    # 2. Staff Master taps Room 1 and Room 2 -> Both Granted
    r_master1 = client.post("/api/access-control/tap", json={"card_uid": master_uid, "room_id": 1})
    r_master2 = client.post("/api/access-control/tap", json={"card_uid": master_uid, "room_id": 2})
    assert r_master1.json()["access_granted"] is True
    assert r_master2.json()["access_granted"] is True

    # 3. Room 2 placed in Maintenance -> Guest key for Room 2 taps Room 2
    guest_r2_uid = f"GUEST-R2-{random.randint(10000, 99999)}"
    client.post("/api/keycards/issue", json={
        "room_id": 2,
        "holder_name": "Locked Out Guest",
        "card_type": "Guest",
        "card_uid": guest_r2_uid,
    })
    client.patch("/rooms/2/status", json={"status": "Maintenance"})

    r_maint_guest = client.post("/api/access-control/tap", json={
        "card_uid": guest_r2_uid,
        "room_id": 2,
    })
    assert r_maint_guest.json()["access_granted"] is False
    assert r_maint_guest.json()["event_type"] == "Denied - Room Locked Out"

    # 4. Master key overrides maintenance lockout
    r_maint_master = client.post("/api/access-control/tap", json={
        "card_uid": master_uid,
        "room_id": 2,
    })
    assert r_maint_master.json()["access_granted"] is True

    # 5. Non-existent card taps Room 1 -> Denied - Invalid Room
    r_unknown = client.post("/api/access-control/tap", json={
        "card_uid": "COMPLETELY-UNKNOWN-NFC-TAG",
        "room_id": 1,
    })
    assert r_unknown.json()["access_granted"] is False
    assert r_unknown.json()["event_type"] == "Denied - Invalid Room"

    # Reset Room 2
    client.patch("/rooms/2/status", json={"status": "Available"})


def test_checkin_auto_issues_keycard_and_checkout_revokes(client):
    """Verify check-in automatically encodes guest keycard and checkout instantly revokes it."""
    client.patch("/rooms/1/status", json={"status": "Available"})

    offset = random.randint(70000, 90000)
    check_in = (date.today() + timedelta(days=offset)).isoformat()
    check_out = (date.today() + timedelta(days=offset + 2)).isoformat()

    booking_payload = {
        "room_id": 1,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": 1,
        "guest": {
            "first_name": "Theresa",
            "last_name": "Vance",
            "email": f"theresa.vance.{offset}@example.com",
            "phone": "+1-555-092-1111",
        }
    }

    # 1. Create reservation
    b_res = client.post("/bookings", json=booking_payload)
    assert b_res.status_code == 201
    booking_id = b_res.json()["id"]

    # 2. Check In
    ci_res = client.post(f"/bookings/{booking_id}/check-in")
    assert ci_res.status_code == 200
    assert ci_res.json()["booking_status"] == "Checked-in"

    # 3. Verify keycard auto-issued
    kc_res = client.get(f"/api/keycards?booking_id={booking_id}")
    assert kc_res.status_code == 200
    cards = kc_res.json()
    assert len(cards) >= 1
    active_card = cards[0]
    assert active_card["status"] == "Active"
    assert active_card["holder_name"] == "Theresa Vance"
    assert active_card["room_id"] == 1
    auto_uid = active_card["card_uid"]

    # 4. Test door tap with auto-issued keycard -> Granted
    tap_res = client.post("/api/access-control/tap", json={
        "card_uid": auto_uid,
        "room_id": 1,
    })
    assert tap_res.json()["access_granted"] is True
    assert tap_res.json()["event_type"] == "Granted"

    # 5. Check Out
    co_res = client.post(f"/bookings/{booking_id}/check-out")
    assert co_res.status_code == 200

    # 6. Verify keycard auto-revoked
    kc_res2 = client.get(f"/api/keycards?booking_id={booking_id}")
    assert kc_res2.status_code == 200
    rev_card = kc_res2.json()[0]
    assert rev_card["status"] == "Revoked"
    assert "Checked Out" in rev_card["revoked_reason"]

    # 7. Test door tap after checkout -> Denied - Card Revoked
    tap_res2 = client.post("/api/access-control/tap", json={
        "card_uid": auto_uid,
        "room_id": 1,
    })
    assert tap_res2.json()["access_granted"] is False
    assert tap_res2.json()["event_type"] == "Denied - Card Revoked"


def test_access_logs_audit_trail(client):
    """Verify GET /api/access-control/logs allows security auditing and filtering."""
    res = client.get("/api/access-control/logs?limit=20")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) >= 1

    sample = logs[0]
    assert "card_uid" in sample
    assert "room_id" in sample
    assert "event_type" in sample
    assert "access_granted" in sample
    assert "attempted_at" in sample

    # Filter by room_id
    res_r1 = client.get("/api/access-control/logs?room_id=1")
    assert res_r1.status_code == 200
    for l in res_r1.json():
        assert l["room_id"] == 1
