import time
import requests

LIVE_URL = "https://grand-horizon-pms.vercel.app"

def test_live_module5():
    print(f"[*] Testing Module 5 Live API on {LIVE_URL}...")
    
    # 1. Dashboard summary
    print("[1] Testing GET /api/access-control/dashboard...")
    r = requests.get(f"{LIVE_URL}/api/access-control/dashboard", timeout=20)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    dash = r.json()
    print(f"Dashboard response: {dash}")
    assert "total_active_cards" in dash
    assert "staff_master_cards" in dash
    assert "total_access_taps_today" in dash
    print("[PASS] Dashboard endpoint verified.")

    # 2. Keycards directory
    print("[2] Testing GET /api/keycards...")
    r = requests.get(f"{LIVE_URL}/api/keycards", timeout=20)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    cards = r.json()
    print(f"Total keycards found: {len(cards)}")
    assert len(cards) >= 1, "Expected at least 1 seeded keycard"
    sample_card = cards[0]
    print(f"Sample card: UID={sample_card.get('card_uid')}, Holder={sample_card.get('holder_name')}, Type={sample_card.get('card_type')}")
    print("[PASS] Keycards directory verified.")

    # 3. Simulate Door Tap (Valid Master Card on Room 1)
    print("[3] Testing POST /api/access-control/tap with Master Card...")
    tap_payload = {
        "card_uid": "RFID-MASTER-001",
        "room_id": 1,
        "reader_location": "Room 101 Penthouse Suite Scanner"
    }
    r = requests.post(f"{LIVE_URL}/api/access-control/tap", json=tap_payload, timeout=20)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    tap_res = r.json()
    print(f"Tap Result: {tap_res}")
    assert tap_res["access_granted"] is True, f"Master key should be granted access: {tap_res}"
    print("[PASS] Door tap simulator verified (Access Granted).")

    # 4. Simulate Door Tap (Invalid / Unrecognized Card)
    print("[4] Testing POST /api/access-control/tap with Unknown Card (Access Denied)...")
    denied_payload = {
        "card_uid": "RFID-ROGUE-9999",
        "room_id": 1,
        "reader_location": "Room 101 Penthouse Suite Scanner"
    }
    r = requests.post(f"{LIVE_URL}/api/access-control/tap", json=denied_payload, timeout=20)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    denied_res = r.json()
    print(f"Denied Result: {denied_res}")
    assert denied_res["access_granted"] is False, f"Unknown card should be denied: {denied_res}"
    print("[PASS] Door tap simulator security denial verified (Access Denied).")

    # 5. Access Logs
    print("[5] Testing GET /api/access-control/logs...")
    r = requests.get(f"{LIVE_URL}/api/access-control/logs", timeout=20)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    logs = r.json()
    print(f"Total access audit events found: {len(logs)}")
    assert len(logs) >= 2, "Expected at least 2 recorded access log entries"
    print("[PASS] Access audit trail logs verified.")

    print("\n[SUCCESS] ALL MODULE 5 LIVE ENDPOINTS VERIFIED OPERATIONAL ON PRODUCTION!")

if __name__ == "__main__":
    test_live_module5()
