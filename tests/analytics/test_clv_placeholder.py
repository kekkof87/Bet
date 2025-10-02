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
    monkeypatch.setenv("ENABLE_CLV_CAPTURE", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()

def _write_alert(tmp_path: Path):
    d = tmp_path / "value_alerts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "value_alerts.json").write_text(
        json.dumps(
            {
                "count": 1,
                "alerts": [
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 800,
                        "value_side": "home_win",
                        "value_edge": 0.08,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

def _write_odds_latest(tmp_path: Path, market):
    d = tmp_path / "odds"
    d.mkdir(parents=True, exist_ok=True)
    (d / "odds_latest.json").write_text(
        json.dumps({"entries": [{"fixture_id": 800, "market": market}]}),
        encoding="utf-8",
    )

def test_clv(tmp_path: Path):
    _write_alert(tmp_path)
    # Opening odds
    _write_odds_latest(tmp_path, {"home_win": 2.10, "draw": 3.5, "away_win": 3.6})
    fixtures = [{"fixture_id": 800, "status": "NS", "home_score": 0, "away_score": 0}]
    build_or_update_roi(fixtures)
    # Closing odds differ
    _write_odds_latest(tmp_path, {"home_win": 2.00, "draw": 3.5, "away_win": 3.7})
    fixtures[0]["status"] = "FT"
    fixtures[0]["home_score"] = 1
    fixtures[0]["away_score"] = 0
    build_or_update_roi(fixtures)
    ledger = json.loads((tmp_path / "roi" / "ledger.json").read_text(encoding="utf-8"))
    pick = ledger[0]
    assert "closing_decimal_odds" in pick
    assert "clv_pct" in pick
    # decimal_odds (apertura) 2.10 -> closing 2.00 => clv negativa
    assert pick["closing_decimal_odds"] == 2.00
