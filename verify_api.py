"""
verify_api.py - Verification script for FastAPI Core & REST Endpoints.
Uses FastAPI's TestClient to test endpoints without requiring an external server process.
"""

from fastapi.testclient import TestClient
from main import app

def verify() -> None:
    # Use TestClient with lifespan context
    with TestClient(app) as client:
        # 1. Test GET /rooms (initial state)
        res = client.get("/rooms")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        rooms = res.json()
        assert len(rooms) >= 5, f"Expected at least 5 rooms, got {len(rooms)}"
        print(f"[PASS] GET /rooms returned {len(rooms)} available rooms.")

        target_room = rooms[0]
        room_id = target_room["id"]
        nightly_rate = target_room["price_per_night"]

        # Use an isolated test date window
        import time
        t_suffix = int(time.time()) % 1000
        test_in = f"2027-01-{(t_suffix % 20) + 1:02d}"
        test_out = f"2027-01-{(t_suffix % 20) + 4:02d}"

        booking_payload = {
            "room_id": room_id,
            "check_in_date": test_in,
            "check_out_date": test_out,
            "guest": {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": f"alice.smith.{t_suffix}@example.com",
                "phone": "+1-555-0144"
            }
        }
        res = client.post("/bookings", json=booking_payload)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        booking = res.json()
        
        # Verify server-side total price calculation: 3 nights * nightly_rate
        expected_total = round(3 * nightly_rate, 2)
        assert booking["total_price"] == expected_total, f"Expected total {expected_total}, got {booking['total_price']}"
        assert booking["booking_status"] == "Confirmed"
        assert booking["room"]["id"] == room_id
        print(f"[PASS] POST /bookings created Booking #{booking['id']} for 3 nights ($ {booking['total_price']}).")

        # 3. Test POST /bookings Double-Booking Prevention (Overlapping dates)
        # Attempt to book the exact same room overlapping the test dates
        conflict_payload = {
            "room_id": room_id,
            "check_in_date": test_in,
            "check_out_date": test_out,
            "guest": {
                "first_name": "Bob",
                "last_name": "Jones",
                "email": f"bob.jones.{t_suffix}@example.com",
                "phone": "+1-555-0177"
            }
        }
        res = client.post("/bookings", json=conflict_payload)
        assert res.status_code == 409, f"Expected 409 Conflict, got {res.status_code}: {res.text}"
        print(f"[PASS] Double-booking rejected with HTTP 409 Conflict: {res.json()['detail']}")

        # 4. Test GET /rooms with date filters excluding booked room
        res = client.get(f"/rooms?check_in_date={test_in}&check_out_date={test_out}")
        assert res.status_code == 200
        available_rooms_during_period = res.json()
        available_ids = [r["id"] for r in available_rooms_during_period]
        assert room_id not in available_ids, f"Booked room {room_id} should not be in available list"
        print(f"[PASS] GET /rooms with date filter correctly excluded booked Room {target_room['room_number']}.")

        # 5. Test Non-Existent Room Handling
        res = client.post("/bookings", json={
            "room_id": 99999,
            "check_in_date": "2026-12-01",
            "check_out_date": "2026-12-03",
            "guest_id": 1
        })
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print(f"[PASS] Booking non-existent room returned HTTP 404.")

    print("\nAll REST API endpoints and lifecycle operations verified successfully!")

if __name__ == "__main__":
    verify()
