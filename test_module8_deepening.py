"""
test_module8_deepening.py - Comprehensive Automated Test Battery for Module 8
Focus: Enterprise KPI Aggregation Engine, Forward-Looking Revenue Forecast,
       Room Category Yield Optimization, and Guest Stay Velocity Analytics
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from main import app
from database import get_db_connection, init_db, seed_rooms, seed_amenities


@pytest.fixture(autouse=True)
def reset_db():
    """Ensure clean database baseline before test execution."""
    init_db()
    seed_rooms()
    seed_amenities()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_core_kpi_analytics_contract_and_ratios(client):
    """Verify standard KPI contract, mathematical formulas, and inventory invariants."""
    res = client.get("/api/analytics/kpis")
    assert res.status_code == 200
    data = res.json()

    # Invariants
    assert data["total_rooms"] == (
        data["available_rooms"]
        + data["occupied_rooms"]
        + data["cleaning_rooms"]
        + data["maintenance_rooms"]
    )
    assert data["active_rooms"] == data["total_rooms"] - data["maintenance_rooms"]

    # Rate math verification
    if data["active_rooms"] > 0:
        expected_occ = round((data["occupied_rooms"] / data["active_rooms"]) * 100.0, 2)
        assert data["occupancy_rate"] == expected_occ
        assert data["occupancy_rate_display"] == f"{expected_occ:.1f}%"

    # RevPAR = ADR * (Occupancy / 100)
    expected_revpar = round(data["adr"] * (data["occupancy_rate"] / 100.0), 2)
    assert data["revpar"] == expected_revpar


def test_revenue_forecast_default_7_days(client):
    """Verify GET /api/analytics/forecast returns a 7-day pacing forecast with accurate date sequence."""
    res = client.get("/api/analytics/forecast")
    assert res.status_code == 200
    data = res.json()

    assert data["forecast_days"] == 7
    assert data["total_active_capacity"] >= 1
    assert "average_projected_occupancy" in data
    assert "total_projected_revenue" in data
    assert len(data["daily_forecasts"]) == 7

    today = date.today()
    for i, df in enumerate(data["daily_forecasts"]):
        expected_date = (today + timedelta(days=i)).isoformat()
        assert df["date"] == expected_date
        assert "day_of_week" in df
        assert df["projected_occupied"] >= 0
        assert df["available_capacity"] >= 0
        assert df["projected_occupied"] + df["available_capacity"] == data["total_active_capacity"]
        assert df["projected_occupancy_rate"] >= 0.0
        assert df["projected_revenue"] >= 0.0


def test_revenue_forecast_custom_horizon_and_validation(client):
    """Verify custom forecast horizon parameter (e.g. 14 days) and bounds checking."""
    # Custom 14-day horizon
    res14 = client.get("/api/analytics/forecast?days=14")
    assert res14.status_code == 200
    data14 = res14.json()
    assert data14["forecast_days"] == 14
    assert len(data14["daily_forecasts"]) == 14

    # Validation: days > 30 should yield 422 Unprocessable Entity
    res_invalid = client.get("/api/analytics/forecast?days=35")
    assert res_invalid.status_code == 422

    # Validation: days < 1 should yield 422
    res_zero = client.get("/api/analytics/forecast?days=0")
    assert res_zero.status_code == 422


def test_room_type_yield_analytics(client):
    """Verify GET /api/analytics/room-types provides accurate category yield breakdowns."""
    res = client.get("/api/analytics/room-types")
    assert res.status_code == 200
    data = res.json()

    assert data["total_categories"] >= 1
    categories = data["categories"]
    assert len(categories) == data["total_categories"]

    category_names = [c["room_type"] for c in categories]
    assert "Single" in category_names or "Double" in category_names

    for cat in categories:
        assert cat["inventory_count"] >= 1
        assert cat["occupied_count"] >= 0
        assert cat["available_count"] >= 0
        assert cat["maintenance_count"] >= 0
        assert cat["avg_price_per_night"] > 0
        assert cat["daily_yield"] == round(cat["occupied_count"] * cat["avg_price_per_night"], 2)
        assert cat["revpar"] == round(cat["daily_yield"] / cat["inventory_count"], 2)


def test_stay_metrics_analytics(client):
    """Verify GET /api/analytics/stay-metrics computes ALOS, status distribution, and cancellation rates."""
    res = client.get("/api/analytics/stay-metrics")
    assert res.status_code == 200
    data = res.json()

    assert "total_bookings" in data
    assert "confirmed_bookings" in data
    assert "completed_bookings" in data
    assert "cancelled_bookings" in data
    assert "cancellation_rate_percent" in data
    assert "average_length_of_stay" in data
    assert "repeat_guest_count" in data
    assert "status_distribution" in data

    assert data["average_length_of_stay"] >= 1.0
    assert 0.0 <= data["cancellation_rate_percent"] <= 100.0
    assert isinstance(data["status_distribution"], dict)


def test_kpis_and_forecast_react_to_new_booking(client):
    """Verify creating a future booking immediately updates both forecast and property metrics."""
    today = date.today()
    in_date = (today + timedelta(days=2)).isoformat()
    out_date = (today + timedelta(days=5)).isoformat()

    # 1. Baseline forecast for day +2
    f_before = client.get("/api/analytics/forecast?days=7").json()
    day2_before = next(d for d in f_before["daily_forecasts"] if d["date"] == in_date)

    # 2. Place a booking spanning day +2 to +5
    booking_res = client.post("/api/bookings", json={
        "guest_id": 1,
        "room_id": 6,
        "check_in_date": in_date,
        "check_out_date": out_date,
    })
    assert booking_res.status_code == 201
    booking_id = booking_res.json()["id"]

    # 3. Forecast for day +2 should show incremented occupancy
    f_after = client.get("/api/analytics/forecast?days=7").json()
    day2_after = next(d for d in f_after["daily_forecasts"] if d["date"] == in_date)
    assert day2_after["projected_occupied"] == day2_before["projected_occupied"] + 1
    assert day2_after["projected_revenue"] > day2_before["projected_revenue"]

    # 4. Cancelling the booking reverts the projected occupancy
    cancel_res = client.post(f"/api/bookings/{booking_id}/cancel")
    assert cancel_res.status_code == 200

    f_revert = client.get("/api/analytics/forecast?days=7").json()
    day2_revert = next(d for d in f_revert["daily_forecasts"] if d["date"] == in_date)
    assert day2_revert["projected_occupied"] == day2_before["projected_occupied"]


def test_maintenance_lockout_impacts_forecast_sellable_capacity(client):
    """Verify taking a room out of order deducts from forecast active sellable capacity."""
    f_base = client.get("/api/analytics/forecast?days=7").json()
    base_cap = f_base["total_active_capacity"]

    # Lockout Room 6 to Out_of_Order
    lock_res = client.post("/api/rooms/6/lockout", json={
        "lockout_type": "Out_of_Order",
        "reason": "Air filtration retrofit",
        "authorized_by": "Ops Manager",
    })
    assert lock_res.status_code == 201

    f_maint = client.get("/api/analytics/forecast?days=7").json()
    assert f_maint["total_active_capacity"] == base_cap - 1

    # Release room back
    rel_res = client.post("/api/rooms/6/release", json={
        "released_by": "Ops Manager",
        "target_cleanliness": "Clean",
    })
    assert rel_res.status_code == 200
    client.patch("/api/rooms/6/status", json={"status": "Available"})
