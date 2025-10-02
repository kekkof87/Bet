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
    monkeypatch.setenv("ENABLE_ROI_ODDS_SNAPSHOT", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_value_alert(tmp_path: Path):
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
                        "fixture_id": 100,
                        "value_side": "home_win",
                        "value_edge": 0.07,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_predictions(tmp_path: Path):
    d = tmp_path / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    (d / "latest_predictions.json").write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "fixture_id": 100,
                        "model_version": "baseline-v1",
                        "prob": {"home_win": 0.5, "draw": 0.3, "away_win": 0.2},
                        "value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.07,
                        },
                        "odds": {
                            "odds_original": {
                                "home_win": 2.10,
                                "draw": 3.40,
                                "away_win": 3.70,
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_odds_latest(tmp_path: Path):
    d = tmp_path / "odds"
    d.mkdir(parents=True, exist_ok=True)
    (d / "odds_latest.json").write_text(
        json.dumps(
            {
                "provider": "stub",
                "entries": [
                    {
                        "fixture_id": 100,
                        "source": "stub-book",
                        "market": {
                            "home_win": 2.1,
                            "draw": 3.5,
                            "away_win": 3.4,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_odds_snapshot_pick(tmp_path: Path):
    _write_value_alert(tmp_path)
    _write_predictions(tmp_path)
    _write_odds_latest(tmp_path)

    fixtures = [
        {
            "fixture_id": 100,
            "home_team": "A",
            "away_team": "B",
            "home_score": 0,
            "away_score": 0,
            "status": "NS",
        }
    ]

    build_or_update_roi(fixtures)

    ledger_path = tmp_path / "roi" / "ledger.json"
    assert ledger_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert len(ledger) == 1
    pick = ledger[0]
    # Snapshot fields
    assert "market_snapshot" in pick
    assert "snapshot_implied" in pick
    assert "snapshot_overround" in pick
    assert "snapshot_at" in pick
    assert "snapshot_provider" in pick
    ms = pick["market_snapshot"]
    assert ms["home_win"] == 2.1
    assert pick["snapshot_provider"] == "stub-book"
