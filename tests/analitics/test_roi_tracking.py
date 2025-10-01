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
    monkeypatch.setenv("ROI_MIN_EDGE", "0.03")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_roi_tracking_picks_and_settlement(tmp_path: Path):
    # Fixtures: one not started, one finished
    fixtures = [
        {
            "fixture_id": 1,
            "home_team": "A",
            "away_team": "B",
            "home_score": 0,
            "away_score": 0,
            "status": "NS",
        },
        {
            "fixture_id": 2,
            "home_team": "C",
            "away_team": "D",
            "home_score": 2,
            "away_score": 1,
            "status": "FT",
        },
    ]

    # Value alerts: one for fixture 1 (pre-match), one for fixture 2 (but already FT -> non crea pick)
    alerts_dir = tmp_path / "value_alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    (alerts_dir / "value_alerts.json").write_text(
        json.dumps(
            {
                "count": 2,
                "alerts": [
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 1,
                        "value_side": "home_win",
                        "value_edge": 0.05,
                    },
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 2,
                        "value_side": "home_win",
                        "value_edge": 0.10,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    build_or_update_roi(fixtures)

    roi_dir = tmp_path / "roi"
    ledger_path = roi_dir / "ledger.json"
    metrics_path = roi_dir / "roi_metrics.json"

    assert ledger_path.exists()
    assert metrics_path.exists()

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    # Only fixture 1 pick created (fixture 2 non NS)
    assert len(ledger) == 1
    assert ledger[0]["fixture_id"] == 1
    assert ledger[0]["settled"] is False

    # Now settle: mark fixture 1 final
    fixtures[0]["home_score"] = 1
    fixtures[0]["away_score"] = 0
    fixtures[0]["status"] = "FT"

    build_or_update_roi(fixtures)
    ledger2 = json.loads(ledger_path.read_text(encoding="utf-8"))
    settled = [p for p in ledger2 if p["fixture_id"] == 1][0]
    assert settled["settled"] is True
    assert settled["result"] in {"win", "loss"}
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "profit_units" in metrics
