"""
test_module11.py - Automated Test Suite for Module 11: Dynamic Pricing & Seasonal Rate Engine
Validates:
1. Dynamic Pricing Quote calculation with day-of-week breakdown
2. Weekend surge multiplier (+20% on Friday & Saturday nights)
3. Summer seasonal surge (+15% in June, July, August)
4. Length-of-stay discounts (10% for >= 5 nights, 15% for >= 7 nights)
5. VIP Loyalty discounts applied to room rates (Silver 5%, Gold 10%, Platinum 15%)
6. Promotional discount coupon creation, validation, minimum spend guardrails, and usage tracking
7. Booking creation with promotional coupon applying net deduction and incrementing redemption count
"""

import sqlite3
from datetime import date
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from main import app, get_db


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    """Isolated database fixture initialized with schema, rooms, amenities, and coupons."""
    test_db = tmp_path / "test_module11.db"
    conn = sqlite3.connect(test_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE Guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        vip_tier TEXT NOT NULL DEFAULT 'Standard',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE Rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
        price_per_night REAL NOT NULL CHECK(price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Cleaning')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE Bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date DATE NOT NULL,
        check_out_date DATE NOT NULL,
        total_price REAL NOT NULL CHECK(total_price >= 0),
        booking_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(booking_status IN ('Confirmed', 'Checked-in', 'Checked-out', 'Cancelled')),
        coupon_code TEXT DEFAULT NULL,
        discount_amount REAL NOT NULL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guest_id) REFERENCES Guests(id) ON DELETE CASCADE,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT
    );
    """)

    cur.execute("""
    CREATE TABLE Amenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price REAL NOT NULL CHECK(price >= 0),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE BookingAmenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        amenity_id INTEGER NOT NULL,
        price_charged REAL NOT NULL CHECK(price_charged >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE CASCADE,
        FOREIGN KEY (amenity_id) REFERENCES Amenities(id) ON DELETE RESTRICT,
        UNIQUE(booking_id, amenity_id)
    );
    """)

    cur.execute("""
    CREATE TABLE Coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        discount_type TEXT NOT NULL CHECK(discount_type IN ('Percentage', 'FixedAmount')),
        discount_value REAL NOT NULL CHECK(discount_value > 0),
        valid_from DATE NOT NULL,
        valid_until DATE NOT NULL,
        min_total REAL NOT NULL DEFAULT 0.0 CHECK(min_total >= 0),
        max_uses INTEGER NOT NULL DEFAULT 100 CHECK(max_uses > 0),
        used_count INTEGER NOT NULL DEFAULT 0 CHECK(used_count >= 0),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK(valid_until >= valid_from)
    );
    """)

    # Seed Room 101 ($100/night) and Room 201 ($200/night)
    cur.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('101', 'Single', 100.0, 'Available');")
    cur.execute("INSERT INTO Rooms (room_number, room_type, price_per_night, status) VALUES ('201', 'Double', 200.0, 'Available');")

    # Seed Amenities
    cur.execute("INSERT INTO Amenities (name, price, description) VALUES ('Executive Breakfast', 25.0, 'Buffet');")

    # Seed Coupons
    cur.execute("""
    INSERT INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active)
    VALUES ('PROMO10', 'Percentage', 10.0, '2026-01-01', '2028-12-31', 100.0, 100, 0, 1);
    """)
    cur.execute("""
    INSERT INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active)
    VALUES ('FIXED25', 'FixedAmount', 25.0, '2026-01-01', '2028-12-31', 150.0, 100, 0, 1);
    """)
    cur.execute("""
    INSERT INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active)
    VALUES ('EXPIRED50', 'FixedAmount', 50.0, '2020-01-01', '2020-12-31', 50.0, 100, 0, 1);
    """)

    # Seed VIP Platinum guest
    cur.execute("""
    INSERT INTO Guests (first_name, last_name, email, phone, vip_tier, notes)
    VALUES ('Victoria', 'Sterling', 'victoria.sterling@royal.uk', '+44-20-7946-0919', 'Platinum', 'Presidential suite preference');
    """)

    conn.commit()
    conn.close()

    def override_get_db():
        c = sqlite3.connect(test_db)
        c.execute("PRAGMA foreign_keys = ON;")
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_pricing_quote_weekend_surge(client: TestClient):
    """
    Room 101 ($100/night):
    Stay from Friday 2026-10-09 to Sunday 2026-10-11 (2 nights: Friday + Saturday).
    Both nights are weekend nights (+20% surge = $20 each).
    Raw room total = $200.
    Weekend surge total = $40.
    Net room charge = $240.
    Tax 10% = $24.
    Grand total = $264.
    """
    req = {
        "room_id": 1,
        "check_in_date": "2026-10-09",
        "check_out_date": "2026-10-11",
    }
    res = client.post("/pricing/quote", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["nights"] == 2
    assert data["raw_room_total"] == 200.0
    assert data["weekend_surge_total"] == 40.0
    assert data["net_room_charge"] == 240.0
    assert data["tax_amount"] == 24.0
    assert data["grand_total"] == 264.0
    assert len(data["nightly_details"]) == 2
    assert all(n["is_weekend"] for n in data["nightly_details"])


def test_pricing_quote_summer_seasonal_surge(client: TestClient):
    """
    Stay in July: 2026-07-06 (Mon) to 2026-07-08 (Wed) = 2 weekday nights.
    Summer surge (+15% = $15/night).
    Weekend surge = $0.
    Raw room total = $200.
    Seasonal surge = $30.
    Net room charge = $230.
    """
    req = {
        "room_id": 1,
        "check_in_date": "2026-07-06",
        "check_out_date": "2026-07-08",
    }
    res = client.post("/pricing/quote", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["seasonal_surge_total"] == 30.0
    assert data["weekend_surge_total"] == 0.0
    assert data["net_room_charge"] == 230.0


def test_pricing_quote_length_of_stay_and_vip_discount(client: TestClient):
    """
    Room 101 ($100/night):
    Stay for 7 nights (2026-11-02 Mon to 2026-11-09 Mon).
    - 5 weekday nights ($100) + 2 weekend nights ($120) = $740 raw adjusted room charge.
    - Length of stay discount (>= 7 nights) = 15% of $740 = $111.00.
    - VIP Platinum discount for Guest #1 = 15% of $740 = $111.00.
    - Net room charge = 740 - 111 - 111 = $518.00.
    """
    req = {
        "room_id": 1,
        "check_in_date": "2026-11-02",
        "check_out_date": "2026-11-09",
        "guest_id": 1,
    }
    res = client.post("/pricing/quote", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["nights"] == 7
    assert data["length_of_stay_discount"] == 111.0
    assert data["vip_discount"] == 111.0
    assert data["net_room_charge"] == 518.0


def test_coupon_validation_endpoint(client: TestClient):
    """Verifies POST /coupons/validate for valid, below minimum, and expired codes."""
    # 1. Valid 10% coupon
    res1 = client.post("/coupons/validate", json={"code": "promo10", "total_amount": 200.0})
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["is_valid"] is True
    assert d1["discount_amount"] == 20.0

    # 2. Below minimum total ($150 min required for FIXED25)
    res2 = client.post("/coupons/validate", json={"code": "FIXED25", "total_amount": 100.0})
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["is_valid"] is False
    assert "Minimum spend" in d2["message"]

    # 3. Expired coupon
    res3 = client.post("/coupons/validate", json={"code": "EXPIRED50", "total_amount": 300.0})
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["is_valid"] is False
    assert "expired" in d3["message"].lower()

    # 4. Unknown code
    res4 = client.post("/coupons/validate", json={"code": "NONEXISTENT", "total_amount": 300.0})
    assert res4.status_code == 200
    assert res4.json()["is_valid"] is False


def test_booking_with_coupon_applies_discount_and_tracks_usage(client: TestClient):
    """
    Creating a booking with PROMO10 on a 2-night stay ($200):
    10% discount = $20 discount.
    Total price = $180.
    Coupon code 'PROMO10' and discount $20 must be persisted.
    Coupons.used_count must increment from 0 to 1.
    """
    booking_payload = {
        "room_id": 1,
        "check_in_date": "2026-10-13",
        "check_out_date": "2026-10-15",
        "guest_id": 1,
        "coupon_code": "PROMO10",
        "apply_dynamic_pricing": False
    }
    res = client.post("/bookings", json=booking_payload)
    assert res.status_code == 201
    booking = res.json()
    assert booking["total_price"] == 180.0
    assert booking["coupon_code"] == "PROMO10"
    assert booking["discount_amount"] == 20.0

    # Check coupon used_count incremented
    coupons = client.get("/coupons?active_only=false").json()
    promo = next(c for c in coupons if c["code"] == "PROMO10")
    assert promo["used_count"] == 1


def test_create_and_list_coupons(client: TestClient):
    """Verifies creating new promotional coupon and listing catalog."""
    new_coupon = {
        "code": "AUTUMN15",
        "discount_type": "Percentage",
        "discount_value": 15.0,
        "valid_from": "2026-09-01",
        "valid_until": "2026-11-30",
        "min_total": 120.0,
        "max_uses": 50,
        "is_active": True
    }
    create_res = client.post("/coupons", json=new_coupon)
    assert create_res.status_code == 201
    c_data = create_res.json()
    assert c_data["code"] == "AUTUMN15"
    assert c_data["discount_value"] == 15.0

    # Duplicate code rejected
    dup_res = client.post("/coupons", json=new_coupon)
    assert dup_res.status_code == 409

    # List coupons includes AUTUMN15
    list_res = client.get("/coupons?active_only=false")
    assert list_res.status_code == 200
    codes = [c["code"] for c in list_res.json()]
    assert "AUTUMN15" in codes
