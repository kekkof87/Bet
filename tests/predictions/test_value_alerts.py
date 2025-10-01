import json
from pathlib import Path

import pytest

from predictions.value_alerts import build_value_alerts, write_value_alerts
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("ENABLE_PREDICTIONS", "1")
    monkeypatch.setenv("ENABLE_CONSENSUS", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_value_alerts_pipeline(tmp_path: Path):
    # predictions
    preds_dir = tmp_path / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    (preds_dir / "latest_predictions.json").write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "fixture_id": 1,
                        "model_version": "baseline-v1",
                        "prob": {"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
                        "value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.05,
                            "deltas": {"home_win": 0.05, "draw": -0.02, "away_win": -0.03},
                        },
                    },
                    {
                        "fixture_id": 2,
                        "model_version": "baseline-v1",
                        "prob": {"home_win": 0.3, "draw": 0.4, "away_win": 0.3},
                        "value": {
                            "active": False,
                            "value_side": "draw",
                            "value_edge": 0.0,
                            "deltas": {"home_win": 0.0, "draw": 0.0, "away_win": 0.0},
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    # consensus
    cons_dir = tmp_path / "consensus"
    cons_dir.mkdir(parents=True, exist_ok=True)
    (cons_dir / "consensus.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "fixture_id": 1,
                        "blended_prob": {"home_win": 0.45, "draw": 0.3, "away_win": 0.25},
                        "consensus_value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.03,
                            "deltas": {"home_win": 0.03, "draw": -0.01, "away_win": -0.02},
                        },
                    },
                    {
                        "fixture_id": 3,
                        "blended_prob": {"home_win": 0.33, "draw": 0.34, "away_win": 0.33},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    alerts = build_value_alerts()
    # Due attivi: prediction fixture 1 + consensus fixture 1 (anche se stesso fixture li consideriamo distinti)
    assert len(alerts) == 2
    out = write_value_alerts(alerts)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert len(data["alerts"]) == 2
