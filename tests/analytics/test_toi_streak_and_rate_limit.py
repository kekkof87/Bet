import json
from pathlib import Path
import pytest
from analytics.roi import build_or_update_roi
from core.config import _reset_settings_cache_for_tests

@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("ROI_MAX_NEW_PICKS_PER_DAY", "2")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()

def _write_value_alerts(tmp_path: Path):
    d = tmp_path / "value_alerts"
    d.mkdir(parents=True, exist_ok=True)
    alerts = []
    for i in range(5):  # 5 alert ma rate limit 2
        alerts.append({
            "source": "prediction",
            "value_type": "prediction_value",
            "fixture_id": 100 + i,
            "value_side": "home_win",
            "value_edge": 0.08,
        })
    (d / "value_alerts.json").write_text(
        json.dumps({"count": len(alerts), "alerts": alerts}), encoding="utf-8"
    )

def test_rate_limit_and_streak(tmp_path: Path):
    _write_value_alerts(tmp_path)
    fixtures = [
        {"fixture_id": 100, "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 101, "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 102, "status": "NS", "home_score": 0, "away_score": 0},
    ]
    build_or_update_roi(fixtures)
    roi_dir = tmp_path / "roi"
    ledger = json.loads((roi_dir / "ledger.json").read_text(encoding="utf-8"))
    # Solo 2 picks create (limite)
    assert len(ledger) == 2
    # Simula settlement
    fixtures[0]["status"] = "FT"
    fixtures[0]["home_score"] = 1
    fixtures[0]["away_score"] = 0
    fixtures[1]["status"] = "FT"
    fixtures[1]["home_score"] = 0
    fixtures[1]["away_score"] = 1
    build_or_update_roi(fixtures)
    metrics = json.loads((roi_dir / "roi_metrics.json").read_text(encoding="utf-8"))
    assert "longest_win_streak" in metrics
    assert "longest_loss_streak" in metrics
