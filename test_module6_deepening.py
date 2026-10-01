import pytest
from fastapi.testclient import TestClient
from api.index import app
from database import init_db, seed_finance_rates_and_taxes

@pytest.fixture(scope="module", autouse=True)
def setup_module6_data():
    init_db()
    seed_finance_rates_and_taxes()

@pytest.fixture
def client():
    return TestClient(app)

def test_exchange_rates_listing_and_base_invariants(client):
    """Verify exchange rates list contains supported global currencies and enforces USD base constraint."""
    res = client.get("/api/finance/exchange-rates")
    assert res.status_code == 200
    rates = res.json()
    assert len(rates) >= 7

    codes = {r["currency_code"]: r for r in rates}
    for expected in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]:
        assert expected in codes

    usd = codes["USD"]
    assert usd["is_base"] is True
    assert usd["rate_to_usd"] == 1.0
    assert usd["symbol"] == "$"

    # Attempting to tamper with USD base rate must fail with 400 Bad Request
    bad_res = client.patch("/api/finance/exchange-rates/USD", json={"rate_to_usd": 1.25})
    assert bad_res.status_code == 400
    assert "Base currency USD" in bad_res.json()["detail"]


def test_exchange_rate_update_and_audit(client):
    """Verify modifying foreign exchange rate updates multiplier and generates audit ledger trail."""
    patch_res = client.patch("/api/finance/exchange-rates/EUR", json={"rate_to_usd": 0.9450})
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["currency_code"] == "EUR"
    assert updated["rate_to_usd"] == 0.9450
    assert updated["updated_at"] is not None

    # Check audit log recorded
    audit_res = client.get("/api/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    rate_logs = [l for l in logs if l.get("action") == "EXCHANGE_RATE_UPDATED"]
    assert len(rate_logs) >= 1
    latest = rate_logs[0]
    assert "EUR" in latest["details"]


def test_currency_conversion_realtime(client):
    """Verify currency conversion calculates correctly through USD base with proper symbol formatting."""
    # 1. USD to EUR
    res_eur = client.post("/api/finance/convert", json={
        "amount": 100.0,
        "from_currency": "USD",
        "to_currency": "EUR"
    })
    assert res_eur.status_code == 200
    data_eur = res_eur.json()
    assert data_eur["from_currency"] == "USD"
    assert data_eur["to_currency"] == "EUR"
    assert data_eur["converted_amount"] == 94.50
    assert data_eur["symbol"] == "€"
    assert "€94.50" in data_eur["formatted_display"]

    # 2. USD to JPY (no decimal places)
    res_jpy = client.post("/api/finance/convert", json={
        "amount": 200.0,
        "from_currency": "USD",
        "to_currency": "JPY"
    })
    assert res_jpy.status_code == 200
    data_jpy = res_jpy.json()
    assert data_jpy["to_currency"] == "JPY"
    assert data_jpy["converted_amount"] == round(200.0 * 152.50)
    assert data_jpy["symbol"] == "¥"
    assert "." not in data_jpy["formatted_display"]

    # 3. Cross currency conversion: JPY to GBP
    res_cross = client.post("/api/finance/convert", json={
        "amount": 15250.0,
        "from_currency": "JPY",
        "to_currency": "GBP"
    })
    assert res_cross.status_code == 200
    data_cross = res_cross.json()
    assert data_cross["from_currency"] == "JPY"
    assert data_cross["to_currency"] == "GBP"
    assert data_cross["converted_amount"] == 79.0


def test_tax_rules_crud_and_lifecycle(client):
    """Verify creation, listing, updating, and deactivation of statutory tax rules."""
    # 1. List initial rules
    list_res = client.get("/api/finance/tax-rules")
    assert list_res.status_code == 200
    rules = list_res.json()
    assert len(rules) >= 3

    # 2. Create new tax rule
    new_rule_payload = {
        "tax_name": "State Luxury Accommodations Tax",
        "tax_type": "Percentage",
        "rate": 3.5,
        "currency_code": "USD",
        "applies_to": "Room_Only",
        "is_active": True
    }
    create_res = client.post("/api/finance/tax-rules", json=new_rule_payload)
    assert create_res.status_code == 201
    created_rule = create_res.json()
    assert created_rule["tax_name"] == "State Luxury Accommodations Tax"
    assert created_rule["rate"] == 3.5
    rule_id = created_rule["id"]

    # 3. Update / Deactivate rule
    update_res = client.patch(f"/api/finance/tax-rules/{rule_id}", json={"is_active": False, "rate": 4.0})
    assert update_res.status_code == 200
    updated_rule = update_res.json()
    assert updated_rule["is_active"] is False
    assert updated_rule["rate"] == 4.0

    # 4. Filter only active rules
    active_res = client.get("/api/finance/tax-rules?is_active=true")
    assert active_res.status_code == 200
    active_ids = [r["id"] for r in active_res.json()]
    assert rule_id not in active_ids


def test_stay_tax_calculation_and_multi_currency_quote(client):
    """Verify full itemized tax computation across room subtotal and incidentals with multi-currency conversion."""
    # Reset EUR rate to 0.92 for standard verification
    client.patch("/api/finance/exchange-rates/EUR", json={"rate_to_usd": 0.9200})

    calc_payload = {
        "room_amount": 300.0,
        "nights": 2,
        "incidentals_amount": 50.0,
        "target_currency": "EUR"
    }

    res = client.post("/api/finance/calculate-tax", json=calc_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["room_subtotal_usd"] == 300.0
    assert data["incidentals_subtotal_usd"] == 50.0
    assert data["subtotal_usd"] == 350.0

    # Taxes expected:
    # 1. Standard Occupancy Sales Tax / VAT (10% on All $350) = $35.00
    # 2. City Tourism Municipal Surcharge ($5/night * 2 nights) = $10.00
    # 3. Eco Sustainability & Green Resort Levy (Flat $12/stay) = $12.00
    # Total tax USD = $57.00
    # Grand total USD = $407.00
    assert data["total_tax_usd"] == 57.00
    assert data["grand_total_usd"] == 407.00

    # EUR conversions:
    assert data["target_currency"] == "EUR"
    assert data["currency_symbol"] == "€"
    assert data["grand_total_converted"] == round(407.00 * 0.92, 2)
    assert "€" in data["formatted_display"]


def test_finance_dashboard_summary(client):
    """Verify finance dashboard endpoint returns consolidated rates, active rules, and blended rate."""
    res = client.get("/api/finance/dashboard")
    assert res.status_code == 200
    dash = res.json()
    assert dash["base_currency"] == "USD"
    assert len(dash["supported_currencies"]) >= 7
    assert len(dash["active_tax_rules"]) >= 3
    assert dash["effective_tax_rate_percent"] >= 10.0
