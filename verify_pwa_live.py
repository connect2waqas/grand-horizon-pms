"""
verify_pwa_live.py - Production verification script for Grand Horizon PWA deployment
"""

import time
import requests

PROD_URL = "https://grand-horizon-pms.vercel.app"

def test_pwa_production():
    print(f"Connecting to Grand Horizon PMS production: {PROD_URL}")
    session = requests.Session()
    session.headers.update({"User-Agent": "Grand-Horizon-PWA-Verifier/1.0"})

    # Wait a few seconds for Vercel deployment to finish
    print("Giving Vercel edge deployment 12 seconds to propagate...")
    time.sleep(12)

    checks_passed = 0
    total_checks = 8

    # 1. Manifest
    r_man = session.get(f"{PROD_URL}/manifest.json", timeout=15)
    print(f"1. GET /manifest.json -> HTTP {r_man.status_code}")
    assert r_man.status_code == 200, f"Expected 200, got {r_man.status_code}"
    m_json = r_man.json()
    assert m_json["short_name"] == "Grand Horizon"
    assert m_json["display"] == "standalone"
    checks_passed += 1
    print("   [OK] Manifest valid & standalone configured")

    # 2. Service Worker
    r_sw = session.get(f"{PROD_URL}/sw.js", timeout=15)
    print(f"2. GET /sw.js -> HTTP {r_sw.status_code}")
    assert r_sw.status_code == 200, f"Expected 200, got {r_sw.status_code}"
    assert "grand-horizon" in r_sw.text
    checks_passed += 1
    print("   [OK] Service worker script live")

    # 3. 192px Icon
    r_ic192 = session.get(f"{PROD_URL}/icon-192.png", timeout=15)
    print(f"3. GET /icon-192.png -> HTTP {r_ic192.status_code} ({len(r_ic192.content)} bytes)")
    assert r_ic192.status_code == 200 and len(r_ic192.content) > 500
    checks_passed += 1
    print("   [OK] Standard 192px app icon verified")

    # 4. 512px Icon
    r_ic512 = session.get(f"{PROD_URL}/icon-512.png", timeout=15)
    print(f"4. GET /icon-512.png -> HTTP {r_ic512.status_code} ({len(r_ic512.content)} bytes)")
    assert r_ic512.status_code == 200 and len(r_ic512.content) > 500
    checks_passed += 1
    print("   [OK] High-resolution 512px app icon verified")

    # 5. Maskable Icons
    r_mask = session.get(f"{PROD_URL}/icon-maskable-192.png", timeout=15)
    print(f"5. GET /icon-maskable-192.png -> HTTP {r_mask.status_code}")
    assert r_mask.status_code == 200
    checks_passed += 1
    print("   [OK] Android adaptive maskable icon verified")

    # 6. Apple Touch Icon
    r_apple = session.get(f"{PROD_URL}/apple-touch-icon.png", timeout=15)
    print(f"6. GET /apple-touch-icon.png -> HTTP {r_apple.status_code}")
    assert r_apple.status_code == 200
    checks_passed += 1
    print("   [OK] iOS Apple Touch Icon verified")

    # 7. HTML Shell Meta tags
    r_html = session.get(f"{PROD_URL}/", timeout=15)
    print(f"7. GET / (App Shell HTML) -> HTTP {r_html.status_code}")
    assert r_html.status_code == 200
    html_text = r_html.text
    assert 'rel="manifest"' in html_text, "Manifest link missing from index.html"
    assert "btnInstallPWA" in html_text, "btnInstallPWA missing from header toolbar"
    checks_passed += 1
    print("   [OK] Manifest tag and #btnInstallPWA present in production HTML")

    # 8. iOS Guidance Modal
    assert "iosInstallModal" in html_text, "iosInstallModal missing from HTML"
    checks_passed += 1
    print("   [OK] iOS Home Screen Guidance Modal present in production HTML")

    print(f"\n========================================================")
    print(f"PWA PRODUCTION VERIFICATION COMPLETE: {checks_passed}/{total_checks} PASSED (100%)")
    print(f"========================================================")

if __name__ == "__main__":
    test_pwa_production()
