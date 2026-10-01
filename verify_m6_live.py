"""
verify_m6_live.py - Module 6 Live Production Verification Script
Tests the deployed Vercel PMS instance for Module 6: Multi-Currency & International Tax Engine
"""
import sys
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

LIVE_URL = "https://grand-horizon-pms.vercel.app"

def test_live_module_6():
    print(f"Testing Module 6 endpoints against live host: {LIVE_URL} ...\n")
    s = requests.Session()
    s.headers.update({"User-Agent": "Module6-LiveVerifier/1.0"})

    # 1. GET /api/finance/exchange-rates
    print("1. Testing GET /api/finance/exchange-rates ...")
    r1 = s.get(f"{LIVE_URL}/api/finance/exchange-rates", timeout=15)
    print(f"   Status: {r1.status_code}")
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
    rates = r1.json()
    assert isinstance(rates, list), "Expected list of rates"
    codes = [r["currency_code"] for r in rates]
    print(f"   Supported currencies: {codes}")
    assert "USD" in codes and "EUR" in codes and "JPY" in codes and "GBP" in codes
    usd_rate = next(r for r in rates if r["currency_code"] == "USD")
    assert usd_rate["rate_to_usd"] == 1.0, f"USD rate should be 1.0, got {usd_rate['rate_to_usd']}"
    print("   ✓ Exchange rates validated.\n")

    # 2. POST /api/finance/convert
    print("2. Testing POST /api/finance/convert (USD to EUR & JPY) ...")
    conv_payload = {
        "amount": 250.0,
        "from_currency": "USD",
        "to_currency": "EUR"
    }
    r2 = s.post(f"{LIVE_URL}/api/finance/convert", json=conv_payload, timeout=15)
    print(f"   Status: {r2.status_code}")
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
    conv_data = r2.json()
    print(f"   Result: {conv_data['original_amount']} USD -> {conv_data['converted_amount']} EUR ({conv_data['formatted_display']})")
    assert conv_data["to_currency"] == "EUR"
    assert conv_data["converted_amount"] > 0
    print("   ✓ Currency conversion validated.\n")

    # 3. GET /api/finance/tax-rules
    print("3. Testing GET /api/finance/tax-rules ...")
    r3 = s.get(f"{LIVE_URL}/api/finance/tax-rules", timeout=15)
    print(f"   Status: {r3.status_code}")
    assert r3.status_code == 200, f"Expected 200, got {r3.status_code}: {r3.text}"
    taxes = r3.json()
    assert isinstance(taxes, list) and len(taxes) >= 3, f"Expected >= 3 tax rules, got {len(taxes)}"
    tax_names = [t["tax_name"] for t in taxes]
    print(f"   Active tax rules: {tax_names}")
    print("   ✓ Statutory tax rules validated.\n")

    # 4. POST /api/finance/calculate-tax
    print("4. Testing POST /api/finance/calculate-tax (Stay tax breakdown with EUR target) ...")
    calc_payload = {
        "room_amount": 500.0,
        "nights": 3,
        "incidentals_amount": 75.0,
        "target_currency": "EUR"
    }
    r4 = s.post(f"{LIVE_URL}/api/finance/calculate-tax", json=calc_payload, timeout=15)
    print(f"   Status: {r4.status_code}")
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}: {r4.text}"
    calc_res = r4.json()
    print(f"   Subtotal: ${calc_res['subtotal_usd']} USD")
    print(f"   Itemized Taxes: {[i['tax_name'] + ' (+$' + str(i['amount_usd']) + ')' for i in calc_res['taxes']]}")
    print(f"   Grand Total USD: ${calc_res['grand_total_usd']}")
    print(f"   Converted Grand Total: {calc_res['formatted_display']} ({calc_res['target_currency']})")
    assert calc_res["grand_total_usd"] > calc_res["subtotal_usd"], "Grand total should include statutory taxes"
    print("   ✓ Itemized tax calculation validated.\n")

    # 5. GET /api/finance/dashboard
    print("5. Testing GET /api/finance/dashboard ...")
    r5 = s.get(f"{LIVE_URL}/api/finance/dashboard", timeout=15)
    print(f"   Status: {r5.status_code}")
    assert r5.status_code == 200, f"Expected 200, got {r5.status_code}: {r5.text}"
    dash = r5.json()
    print(f"   Supported currencies count: {len(dash['supported_currencies'])}")
    print(f"   Active tax rules count: {len(dash['active_tax_rules'])}")
    print(f"   Effective Tax Rate: {dash['effective_tax_rate_percent']}%")
    assert dash["base_currency"] == "USD"
    print("   ✓ Finance dashboard consolidated summary validated.\n")

    print("=================================================================")
    print("ALL MODULE 6 LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY! (5/5)")
    print("=================================================================")

if __name__ == "__main__":
    test_live_module_6()
