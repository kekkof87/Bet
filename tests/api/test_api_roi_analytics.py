from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from analytics.roi import save_ledger, compute_metrics
from core.config import _reset_settings_cache_for_tests, get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_ROI_EDGE_DECILES", "1")
    monkeypatch.setenv("ENABLE_ROI_CLV_AGGREGATE", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    return TestClient(create_app())


def test_analytics_endpoint(client, tmp_path: Path):
    settings = get_settings()
    roi_dir = Path(settings.bet_data_dir) / settings.roi_dir
    roi_dir.mkdir(parents=True, exist_ok=True)
    ledger = [
        {
            "created_at": "2025-10-01T10:00:00Z",
            "fixture_id": 1,
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 2.0,
            "edge": 0.07,
            "settled": True,
            "result": "win",
            "payout": 2.0,
            "clv_pct": 0.03,
            "settled_at": "2025-10-01T10:00:00Z",
        }
    ]
    save_ledger(roi_dir, ledger)
    compute_metrics(ledger)  # produce metrics file

    r = client.get("/roi/analytics")
    assert r.status_code == 200
    js = r.json()
    assert js["enabled"] is True
    assert "rolling" in js
    assert "clv" in js
    assert "edge_deciles" in js
