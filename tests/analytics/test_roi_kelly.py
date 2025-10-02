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
    monkeypatch.setenv("ENABLE_KELLY_STAKING", "1")
    monkeypatch.setenv("KELLY_BASE_UNITS", "1.0")
    monkeypatch.setenv("KELLY_MAX_UNITS", "2.0")
    monkeypatch.setenv("KELLY_EDGE_CAP", "0.5")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_predictions(tmp_path: Path):
    preds_dir = tmp_path / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    # fixture 10: model prob home_win 0.55
    (preds_dir / "latest_predictions.json").write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "fixture_id": 10,
                        "model_version": "baseline-v1",
                        "prob": {"home_win": 0.55, "draw": 0.25, "away_win": 0.20},
                        "value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.08,
                        },
                        "odds": {
                            "odds_original": {
                                "home_win": 2.2,
                                "draw": 3.5,
                                "away_win": 3.4,
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_value_alerts(tmp_path: Path):
    alerts_dir = tmp_path / "value_alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    (alerts_dir / "value_alerts.json").write_text(
        json.dumps(
            {
                "count": 1,
                "alerts": [
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 10,
                        "value_side": "home_win",
                        "value_edge": 0.08,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_kelly_stake(tmp_path: Path):
    _write_predictions(tmp_path)
    _write_value_alerts(tmp_path)

    fixtures = [
        {
            "fixture_id": 10,
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
    assert pick["stake_strategy"] in {"kelly", "fixed"}
    # Calcolo atteso fraction (2.2 * 0.55 - 1) / (1.2) = (1.21 - 1)/1.2 = 0.21/1.2 = 0.175
    # Stake = 0.175 * base(1.0) = 0.175
    assert abs(pick["stake"] - 0.175) < 0.001
    assert abs(pick["kelly_fraction"] - 0.175) < 0.001
    assert abs(pick["kelly_fraction_capped"] - 0.175) < 0.001
    assert pick["kelly_prob"] == 0.55
