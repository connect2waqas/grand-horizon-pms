"""
test_module8.py - Automated Test Suite for Module 8
Focus: Enterprise KPI Aggregation Engine (GET /analytics/kpis, Occupancy Rate, ADR, RevPAR)
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_kpis_contract_and_structure(client):
    """Verify that GET /analytics/kpis returns the full KPIAnalyticsResponse contract."""
    response = client.get("/analytics/kpis")
    assert response.status_code == 200
    data = response.json()

    # Core inventory keys
    assert "total_rooms" in data
    assert "active_rooms" in data
    assert "available_rooms" in data
    assert "occupied_rooms" in data
    assert "cleaning_rooms" in data
    assert "maintenance_rooms" in data

    # Financial / Performance keys
    assert "occupancy_rate" in data
    assert "occupancy_rate_display" in data
    assert "adr" in data
    assert "revpar" in data
    assert "total_revenue" in data
    assert "monthly_revenue" in data

    # Turnover keys
    assert "today_checkins" in data
    assert "today_checkouts" in data

    # Integrity assertions
    assert data["total_rooms"] == (
        data["available_rooms"]
        + data["occupied_rooms"]
        + data["cleaning_rooms"]
        + data["maintenance_rooms"]
    )
    assert data["active_rooms"] == data["total_rooms"] - data["maintenance_rooms"]


def test_occupancy_rate_and_display(client):
    """Verify accurate occupancy rate computation."""
    response = client.get("/analytics/kpis")
    assert response.status_code == 200
    data = response.json()

    active = data["active_rooms"]
    occupied = data["occupied_rooms"]
    if active > 0:
        expected_rate = round((occupied / active) * 100, 2)
        assert data["occupancy_rate"] == expected_rate
        assert data["occupancy_rate_display"] == f"{expected_rate:.1f}%"


def test_adr_and_revpar_calculation(client):
    """Verify that ADR and RevPAR reflect hotel revenue management formulas."""
    response = client.get("/analytics/kpis")
    assert response.status_code == 200
    data = response.json()

    adr = data["adr"]
    occ_rate = data["occupancy_rate"]
    expected_revpar = round(adr * (occ_rate / 100.0), 2)
    assert data["revpar"] == expected_revpar


def test_kpi_engine_reacts_dynamically_to_room_status_mutations(client):
    """Verify that room turnover directly updates Occupancy, ADR, and RevPAR in real time."""
    # 0. Ensure clean baseline
    client.patch("/rooms/1/status", json={"status": "Available"})

    # 1. Get baseline
    base_kpi = client.get("/analytics/kpis").json()
    base_occupied = base_kpi["occupied_rooms"]

    # 2. Mark Room 1 as Occupied
    patch_res = client.patch("/rooms/1/status", json={"status": "Occupied"})
    assert patch_res.status_code == 200

    new_kpi = client.get("/analytics/kpis").json()
    assert new_kpi["occupied_rooms"] == base_occupied + 1
    assert new_kpi["occupancy_rate"] > base_kpi["occupancy_rate"]
    assert new_kpi["revpar"] >= base_kpi["revpar"]

    # 3. Mark Room 1 as Cleaning (no longer occupied)
    client.patch("/rooms/1/status", json={"status": "Cleaning"})
    clean_kpi = client.get("/analytics/kpis").json()
    assert clean_kpi["occupied_rooms"] == base_occupied
    assert clean_kpi["cleaning_rooms"] == base_kpi["cleaning_rooms"] + 1

    # 4. Cleanup: Revert Room 1 to Available
    client.patch("/rooms/1/status", json={"status": "Available"})


def test_maintenance_room_adjusts_active_inventory(client):
    """Verify that setting a room to Maintenance deducts from active rooms and recalculates occupancy denominator."""
    client.patch("/rooms/2/status", json={"status": "Available"})
    base_kpi = client.get("/analytics/kpis").json()
    base_active = base_kpi["active_rooms"]
    base_maint = base_kpi["maintenance_rooms"]

    # Flag Room 2 as Maintenance
    client.patch("/rooms/2/status", json={"status": "Maintenance"})

    maint_kpi = client.get("/analytics/kpis").json()
    assert maint_kpi["maintenance_rooms"] == base_maint + 1
    assert maint_kpi["active_rooms"] == base_active - 1

    # Cleanup: Revert Room 2
    client.patch("/rooms/2/status", json={"status": "Available"})


def test_stats_backward_compatibility(client):
    """Verify that legacy GET /stats remains consistent with GET /analytics/kpis."""
    stats = client.get("/stats").json()
    kpis = client.get("/analytics/kpis").json()

    assert stats["total_rooms"] == kpis["total_rooms"]
    assert stats["occupancy_rate"] == kpis["occupancy_rate_display"]
    assert stats["est_revenue"] == kpis["total_revenue"]
