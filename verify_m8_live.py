"""
verify_m8_live.py - Live Production Verification for Module 8
Tests all Module 8 endpoints on https://grand-horizon-pms.vercel.app/
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

print("\n=== Grand Horizon PMS - Module 8 Live Production Verification ===\n")

# --- Test 1: GET /api/analytics/kpis ----------------------------------------
print("1. GET /api/analytics/kpis - Consolidated property performance KPIs")
try:
    r = requests.get(f"{BASE}/api/analytics/kpis", timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("Has total_rooms", "total_rooms" in d and d["total_rooms"] >= 1)
        check("Has occupancy_rate", "occupancy_rate" in d)
        check("Has occupancy_rate_display", "occupancy_rate_display" in d)
        check("Has adr", "adr" in d)
        check("Has revpar", "revpar" in d)
        check("Has total_revenue", "total_revenue" in d)
        print(f"     Rooms: {d['total_rooms']} | Occ: {d['occupancy_rate_display']} | ADR: ${d['adr']} | RevPAR: ${d['revpar']}")
except Exception as e:
    check("KPIs request succeeded", False, str(e))

time.sleep(1)

# --- Test 2: GET /api/analytics/forecast (7 Days) ---------------------------
print("\n2. GET /api/analytics/forecast - 7-Day forward pacing forecast")
try:
    r = requests.get(f"{BASE}/api/analytics/forecast", timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("forecast_days is 7", d.get("forecast_days") == 7)
        check("Has total_active_capacity", "total_active_capacity" in d and d["total_active_capacity"] >= 1)
        check("Has average_projected_occupancy", "average_projected_occupancy" in d)
        check("daily_forecasts is 7 items", len(d.get("daily_forecasts", [])) == 7)
        first_day = d["daily_forecasts"][0] if d.get("daily_forecasts") else {}
        check("Daily item has date & day_of_week", "date" in first_day and "day_of_week" in first_day)
        check("Daily item has projected_occupancy_rate", "projected_occupancy_rate" in first_day)
        print(f"     Horizon: {d['forecast_days']}d | Avg Occ: {d['average_projected_occupancy']}% | Rev: ${d['total_projected_revenue']}")
except Exception as e:
    check("Forecast request succeeded", False, str(e))

time.sleep(1)

# --- Test 3: GET /api/analytics/forecast?days=14 ----------------------------
print("\n3. GET /api/analytics/forecast?days=14 - Extended 14-day horizon")
try:
    r = requests.get(f"{BASE}/api/analytics/forecast", params={"days": 14}, timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("forecast_days is 14", d.get("forecast_days") == 14)
        check("daily_forecasts is 14 items", len(d.get("daily_forecasts", [])) == 14)
except Exception as e:
    check("Extended forecast succeeded", False, str(e))

time.sleep(1)

# --- Test 4: GET /api/analytics/room-types ----------------------------------
print("\n4. GET /api/analytics/room-types - Category yield and RevPAR breakdown")
try:
    r = requests.get(f"{BASE}/api/analytics/room-types", timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("Has total_categories", d.get("total_categories", 0) >= 1)
        check("categories list non-empty", len(d.get("categories", [])) >= 1)
        c0 = d["categories"][0] if d.get("categories") else {}
        check("Category has room_type", "room_type" in c0)
        check("Category has avg_price_per_night", "avg_price_per_night" in c0)
        check("Category has revpar", "revpar" in c0)
        print(f"     Categories: {d['total_categories']} ({', '.join(c['room_type'] for c in d.get('categories', []))})")
except Exception as e:
    check("Room-types request succeeded", False, str(e))

time.sleep(1)

# --- Test 5: GET /api/analytics/stay-metrics --------------------------------
print("\n5. GET /api/analytics/stay-metrics - Guest booking velocity & stay behavior")
try:
    r = requests.get(f"{BASE}/api/analytics/stay-metrics", timeout=20)
    check("HTTP 200 OK", r.status_code == 200, f"Got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        check("Has total_bookings", "total_bookings" in d)
        check("Has average_length_of_stay", "average_length_of_stay" in d and d["average_length_of_stay"] >= 1.0)
        check("Has cancellation_rate_percent", "cancellation_rate_percent" in d)
        check("Has status_distribution", isinstance(d.get("status_distribution"), dict))
        print(f"     Bookings: {d['total_bookings']} | ALOS: {d['average_length_of_stay']}n | Cancel Rate: {d['cancellation_rate_percent']}%")
except Exception as e:
    check("Stay-metrics request succeeded", False, str(e))

# --- Summary -----------------------------------------------------------------
total = len(results)
passed = sum(results)
print(f"\n{'='*60}")
print(f"Module 8 Live Verification: {passed}/{total} checks passed")
if passed == total:
    print("  [SUCCESS] ALL CHECKS PASSED - Module 8 is LIVE and VERIFIED!")
else:
    print(f"  [WARNING] {total - passed} check(s) failed.")
print(f"{'='*60}\n")
sys.exit(0 if passed == total else 1)
