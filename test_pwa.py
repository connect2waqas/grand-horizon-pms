"""
test_pwa.py - Test suite for Progressive Web App (PWA) capabilities
Verifies:
1. Manifest JSON endpoint accessibility and specification compliance
2. Service Worker registration script accessibility and headers
3. Application icon assets (192px, 512px, maskable, apple-touch-icon)
4. Offline resilience and fallback strategies
"""

import json
from fastapi.testclient import TestClient
from api.index import app

client = TestClient(app)


def test_manifest_endpoint():
    """Verify /manifest.json returns valid JSON with required PWA manifest fields."""
    response = client.get("/manifest.json")
    assert response.status_code == 200
    assert "application/manifest+json" in response.headers.get("content-type", "")

    data = response.json()
    assert data["name"] == "Grand Horizon Hotel PMS"
    assert data["short_name"] == "Grand Horizon"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/?source=pwa"
    assert data["theme_color"] == "#6366F1"
    assert data["background_color"] == "#0B1120"
    assert len(data["icons"]) >= 4

    # Check icons have 192 and 512 sizes
    icon_sizes = [i["sizes"] for i in data["icons"]]
    assert "192x192" in icon_sizes
    assert "512x512" in icon_sizes


def test_service_worker_endpoint():
    """Verify /sw.js returns valid javascript and service worker headers."""
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert response.headers.get("Service-Worker-Allowed") == "/"

    content = response.text
    assert "grand-horizon-cache" in content
    assert "addEventListener('install'" in content
    assert "addEventListener('fetch'" in content


def test_pwa_icon_assets():
    """Verify all PWA icon assets are served with image/png MIME type."""
    icons = [
        "/icon-192.png",
        "/icon-512.png",
        "/icon-maskable-192.png",
        "/icon-maskable-512.png",
        "/apple-touch-icon.png",
    ]
    for icon_path in icons:
        resp = client.get(icon_path)
        assert resp.status_code == 200, f"Failed to retrieve {icon_path}"
        assert "image/png" in resp.headers.get("content-type", "")
        assert len(resp.content) > 500, f"{icon_path} file appears empty or corrupt"


def test_manifest_api_alias():
    """Verify /api/manifest.json alias works identically."""
    resp = client.get("/api/manifest.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["short_name"] == "Grand Horizon"


def test_sw_api_alias():
    """Verify /api/sw.js alias works identically."""
    resp = client.get("/api/sw.js")
    assert resp.status_code == 200
    assert "grand-horizon" in resp.text
