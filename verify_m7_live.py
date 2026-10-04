"""
verify_m7_live.py - Live Production Verification for Module 7
Tests all Module 7 endpoints on https://grand-horizon-pms.vercel.app/
"""
import sys
import requests
import time

BASE = "https://grand-horizon-pms.vercel.app"
PASS = "[PASS]"
FAIL = "[FAIL]"

results = []

def check(label, cond, detail=""):
    icon = PASS if cond else FAIL
    print(f"  {icon} {label}" + (f" - {detail}" if detail else ""))
    results.append(cond)

print("\n=== Grand Horizon PMS - Module 7 Live Production Verification ===\n")

# 0. Find an Available room for lockout testing
target_room_id = 6
try:
    rooms_res = requests.get(f"{BASE}/api/rooms", timeout=15)
    if rooms_res.status_code == 200:
        rooms = rooms_res.json()
        avail_rooms = [rm for rm in rooms if rm.get("status") in ("Available", "Cleaning")]
        if avail_rooms:
            target_room_id = avail_rooms[0]["id"]
            print(f"Found non-occupied test room: ID {target_room_id} (Room {avail_rooms[0].get('room_number')})")
        else:
            print(f"Defaulting to Room ID {target_room_id}")
except Exception as e:
    print(f"Rooms lookup note: {e}")

# --- Test 1: Declare Room Lockout -------------------------------------------
print(f"\n1. POST /api/rooms/{target_room_id}/lockout - Decommission room to Out-of-Order")
try:
    r = requests.post(f"{BASE}/api/rooms/{target_room_id}/lockout", json={
        "lockout_type": "Out_of_Order",
        "reason": "Live verification: Guest bathroom pipe fracture",
        "assigned_trade": "Plumbing Specialists",
        "authorized_by": "Duty Manager (M7 Verify)",
        "notes": "Automated live prod test fixture",
    }, timeout=25)
    check("HTTP 201 Created", r.status_code == 201, f"Got {r.status_code}: {r.text[:200]}")
    if r.status_code == 201:
        d = r.json()
        check("room_id matches", d.get("room_id") == target_room_id)
        check("lockout_type is Out_of_Order", d.get("lockout_type") == "Out_of_Order")
        check("is_active is True", d.get("is_active") is True)
        print(f"     Lockout ID: {d.get('id')}, Room: {d.get('room_number')}")
except Exception as e:
    check("Lockout request succeeded", False, str(e))

time.sleep(1)

# --- Test 2: GET lockouts registry ------------------------------------------
print("\n2. GET /api/rooms/lockouts?is_active=true - Active lockout registry")
try:
    r = requests.get(f"{BASE}/api/rooms/lockouts", params={"is_active": "true"}, timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Returns list", isinstance(data, list))
        check("At least 1 active lockout", len(data) >= 1, f"Found {len(data)}")
        print(f"     Active lockouts: {len(data)}")
except Exception as e:
    check("Lockouts list request succeeded", False, str(e))

time.sleep(1)

# --- Test 3: Release Room Lockout --------------------------------------------
print(f"\n3. POST /api/rooms/{target_room_id}/release - Certify repair and return to Cleaning")
try:
    r = requests.post(f"{BASE}/api/rooms/{target_room_id}/release", json={
        "released_by": "Lead Technician (M7 Verify)",
        "target_cleanliness": "Touch-up Required",
        "resolution_notes": "Pipe fracture repaired. Pressure tested. Ready for turnover.",
    }, timeout=25)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        check("is_active becomes False", d.get("is_active") is False)
        check("resolved_by populated", bool(d.get("resolved_by")))
        print(f"     Released by: {d.get('resolved_by')}")
except Exception as e:
    check("Release request succeeded", False, str(e))

time.sleep(1)

# --- Test 4: Room Operations Dashboard ---------------------------------------
print("\n4. GET /api/rooms/operations-dashboard - Consolidated cockpit metrics")
try:
    r = requests.get(f"{BASE}/api/rooms/operations-dashboard", timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("Has total_rooms", "total_rooms" in d)
        check("Has available_count", "available_count" in d)
        check("Has occupied_count", "occupied_count" in d)
        check("Has out_of_order_count", "out_of_order_count" in d)
        check("active_lockouts is list", isinstance(d.get("active_lockouts"), list))
        check("recent_room_moves is list", isinstance(d.get("recent_room_moves"), list))
        print(f"     Rooms: {d['total_rooms']} total | {d['available_count']} available | {d['occupied_count']} occupied | {d.get('out_of_order_count',0)} OOO")
except Exception as e:
    check("Dashboard request succeeded", False, str(e))

# --- Summary -----------------------------------------------------------------
total = len(results)
passed = sum(results)
print(f"\n{'='*60}")
print(f"Module 7 Live Verification: {passed}/{total} checks passed")
if passed == total:
    print("  [SUCCESS] ALL CHECKS PASSED - Module 7 is LIVE and VERIFIED!")
else:
    print(f"  [WARNING] {total - passed} check(s) failed.")
print(f"{'='*60}\n")
sys.exit(0 if passed == total else 1)
