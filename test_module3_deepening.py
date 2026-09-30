"""
test_module3_deepening.py - Automated Test Suite for Module 3 Deepening
Focus: Rates, Dynamic Pricing & Yield Management
- Rate plan catalog retrieval (BAR, Non-Refundable, B&B, Extended Stay)
- Custom rate plan creation & duplicate code conflict validation
- Dynamic pricing quotes modulated by rate plan multipliers and cancellation policies
- Minimum Length of Stay (MLOS) restriction verification & booking enforcement (HTTP 422)
- Occupancy-driven yield management demand surge computation & tiers
- Rate plan persistence and retrieval in booking records
"""

import random
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db_connection
from schemas import DemandYieldTier, CancellationPolicy, MealPlanType


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_rate_plans_catalog(client: TestClient):
    """Verify retrieval of seeded rate plans with multipliers, policies, and MLOS."""
    res = client.get("/rates/plans")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) >= 4

    plan_codes = {p["code"] for p in plans}
    assert "BAR" in plan_codes
    assert "NON_REF" in plan_codes
    assert "BB_PACKAGE" in plan_codes
    assert "CORP_EXTENDED" in plan_codes

    bar = next(p for p in plans if p["code"] == "BAR")
    assert bar["rate_multiplier"] == 1.0
    assert bar["min_los"] == 1
    assert "Flexible" in bar["cancellation_policy"]

    non_ref = next(p for p in plans if p["code"] == "NON_REF")
    assert non_ref["rate_multiplier"] == 0.85
    assert "Non-Refundable" in non_ref["cancellation_policy"]

    corp = next(p for p in plans if p["code"] == "CORP_EXTENDED")
    assert corp["min_los"] == 3


def test_create_custom_rate_plan(client: TestClient):
    """Verify creation of a custom rate plan and conflict on duplicate code."""
    unique_suffix = random.randint(1000, 9999)
    code = f"VIP_CONF_{unique_suffix}"

    payload = {
        "code": code,
        "name": f"VIP Conference Special {unique_suffix}",
        "description": "Exclusive rate for tech conference attendees with full board.",
        "rate_multiplier": 0.90,
        "cancellation_policy": CancellationPolicy.MODERATE.value,
        "meal_plan": MealPlanType.FULL_BOARD.value,
        "min_los": 2,
        "is_active": True,
    }

    res = client.post("/rates/plans", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["code"] == code
    assert created["rate_multiplier"] == 0.90
    assert created["meal_plan"] == MealPlanType.FULL_BOARD.value
    assert created["min_los"] == 2

    # Duplicate creation should return 409 Conflict
    dup_res = client.post("/rates/plans", json=payload)
    assert dup_res.status_code == 409


def test_dynamic_pricing_quote_with_rate_plans(client: TestClient):
    """
    Test dynamic pricing quotes comparing BAR, NON_REF, and BB_PACKAGE.
    Room 1, 2 weekday nights.
    """
    rooms = client.get("/rooms").json()
    room_info = next(r for r in rooms if r["id"] == 1)
    base_rate = float(room_info["price_per_night"])

    # 1. Best Available Rate (BAR - 1.0 multiplier)
    quote_bar = client.post(
        "/rates/quote",
        json={
            "room_id": 1,
            "check_in_date": "2026-11-09",
            "check_out_date": "2026-11-11",
            "rate_plan_code": "BAR",
        },
    ).json()
    expected_bar_total = round(base_rate * 2, 2)
    assert quote_bar["rate_plan_code"] == "BAR"
    assert quote_bar["raw_room_total"] == expected_bar_total
    assert quote_bar["rate_plan_adjustment"] == 0.0
    assert quote_bar["min_los_met"] is True

    # 2. Non-Refundable (NON_REF - 0.85 multiplier)
    quote_non_ref = client.post(
        "/rates/quote",
        json={
            "room_id": 1,
            "check_in_date": "2026-11-09",
            "check_out_date": "2026-11-11",
            "rate_plan_code": "NON_REF",
        },
    ).json()
    expected_non_ref_nightly = round(base_rate * 0.85, 2)
    expected_non_ref_total = round(expected_non_ref_nightly * 2, 2)
    assert quote_non_ref["rate_plan_code"] == "NON_REF"
    assert quote_non_ref["raw_room_total"] == expected_non_ref_total
    assert quote_non_ref["rate_plan_adjustment"] == round(expected_non_ref_total - (base_rate * 2), 2)
    assert "Non-Refundable" in quote_non_ref["cancellation_policy"]

    # 3. Bed & Breakfast Package (BB_PACKAGE - 1.15 multiplier)
    quote_bb = client.post(
        "/rates/quote",
        json={
            "room_id": 1,
            "check_in_date": "2026-11-09",
            "check_out_date": "2026-11-11",
            "rate_plan_code": "BB_PACKAGE",
        },
    ).json()
    expected_bb_nightly = round(base_rate * 1.15, 2)
    expected_bb_total = round(expected_bb_nightly * 2, 2)
    assert quote_bb["rate_plan_code"] == "BB_PACKAGE"
    assert quote_bb["raw_room_total"] == expected_bb_total
    assert quote_bb["rate_plan_adjustment"] == round(expected_bb_total - (base_rate * 2), 2)
    assert quote_bb["meal_plan"] == MealPlanType.CONTINENTAL_BREAKFAST.value


def test_mlos_restriction_quote_and_booking_enforcement(client: TestClient):
    """
    CORP_EXTENDED has min_los = 3 nights.
    - 1 night quote: min_los_met is False.
    - 1 night booking attempt: rejected with HTTP 422 Unprocessable Content.
    - 3 nights booking attempt: accepted with HTTP 201 Created.
    """
    client.patch("/rooms/1/status", json={"status": "Available"})

    offset = random.randint(4000, 6000)
    check_in_1n = (date.today() + timedelta(days=offset)).isoformat()
    check_out_1n = (date.today() + timedelta(days=offset + 1)).isoformat()

    # 1. Quote check
    quote_res = client.post(
        "/rates/quote",
        json={
            "room_id": 1,
            "check_in_date": check_in_1n,
            "check_out_date": check_out_1n,
            "rate_plan_code": "CORP_EXTENDED",
        },
    )
    assert quote_res.status_code == 200
    quote_data = quote_res.json()
    assert quote_data["min_los_met"] is False
    assert quote_data["min_los_required"] == 3

    # 2. 1-Night Booking attempt fails with 422
    booking_1n = {
        "room_id": 1,
        "check_in_date": check_in_1n,
        "check_out_date": check_out_1n,
        "rate_plan_code": "CORP_EXTENDED",
        "guest": {
            "first_name": "Marcus",
            "last_name": "Vance",
            "email": f"marcus.vance.{offset}@example.com",
            "phone": "+1-555-444-1234",
            "vip_tier": "Standard",
        },
    }
    fail_res = client.post("/bookings", json=booking_1n)
    assert fail_res.status_code == 422
    assert "minimum stay of 3 nights" in fail_res.json()["detail"]

    # 3. 3-Nights Booking attempt succeeds with 201
    check_out_3n = (date.today() + timedelta(days=offset + 3)).isoformat()
    booking_3n = {
        "room_id": 1,
        "check_in_date": check_in_1n,
        "check_out_date": check_out_3n,
        "rate_plan_code": "CORP_EXTENDED",
        "guest": {
            "first_name": "Marcus",
            "last_name": "Vance",
            "email": f"marcus.vance.{offset}@example.com",
            "phone": "+1-555-444-1234",
            "vip_tier": "Standard",
        },
    }
    success_res = client.post("/bookings", json=booking_3n)
    assert success_res.status_code == 201
    saved_booking = success_res.json()
    assert saved_booking["rate_plan_code"] == "CORP_EXTENDED"

    # Verify retrieval
    b_id = saved_booking["id"]
    get_res = client.get(f"/bookings/{b_id}")
    assert get_res.status_code == 200
    assert get_res.json()["rate_plan_code"] == "CORP_EXTENDED"


def test_occupancy_demand_surge_calculation(client: TestClient):
    """Verify that compute_occupancy_yield calculates demand tiers and surges properly."""
    conn = get_db_connection()
    try:
        from api.index import compute_occupancy_yield

        # Far-future interval with 0 bookings should be LOW_DEMAND (0.0 surge)
        far_ci = date.today() + timedelta(days=9000)
        far_co = date.today() + timedelta(days=9002)

        occ_pct, tier, surge = compute_occupancy_yield(conn, far_ci, far_co)
        assert occ_pct == 0.0
        assert tier == DemandYieldTier.LOW_DEMAND
        assert surge == 0.0

        # Test quote response structure contains demand_tier and occupancy_rate
        quote_res = client.post(
            "/pricing/quote",
            json={
                "room_id": 1,
                "check_in_date": far_ci.isoformat(),
                "check_out_date": far_co.isoformat(),
                "rate_plan_code": "BAR",
            },
        )
        assert quote_res.status_code == 200
        q = quote_res.json()
        assert "occupancy_rate" in q
        assert "demand_tier" in q
        assert q["demand_tier"] == DemandYieldTier.LOW_DEMAND.value
        assert q["occupancy_surge_total"] == 0.0
    finally:
        conn.close()
