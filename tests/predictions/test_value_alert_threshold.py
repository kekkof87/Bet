import json
from pathlib import Path
import pytest

from core.config import _reset_settings_cache_for_tests
from predictions.value_alerts import build_value_alerts, write_value_alerts


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("VALUE_ALERT_MIN_EDGE", "0.08")  # threshold più alto del default 0.05
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_predictions(tmp_path: Path):
    preds_dir = tmp_path / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "predictions": [
            {
                "fixture_id": 1,
                "model_version": "baseline-v1",
                "prob": {"home_win": 0.5, "draw": 0.25, "away_win": 0.25},
                "value": {"active": True, "value_side": "home_win", "value_edge": 0.04},
            },
            {
                "fixture_id": 2,
                "model_version": "baseline-v1",
                "prob": {"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
                "value": {"active": True, "value_side": "draw", "value_edge": 0.09},
            },
        ]
    }
    (preds_dir / "latest_predictions.json").write_text(json.dumps(data), encoding="utf-8")


def _write_consensus(tmp_path: Path):
    cons_dir = tmp_path / "consensus"
    cons_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "entries": [
            {
                "fixture_id": 3,
                "consensus_value": {
                    "active": True,
                    "value_side": "away_win",
                    "value_edge": 0.07,
                },
            },
            {
                "fixture_id": 4,
                "consensus_value": {
                    "active": True,
                    "value_side": "home_win",
                    "value_edge": 0.12,
                },
            },
        ]
    }
    (cons_dir / "consensus.json").write_text(json.dumps(data), encoding="utf-8")


def test_value_alert_threshold(tmp_path: Path):
    _write_predictions(tmp_path)
    _write_consensus(tmp_path)

    alerts = build_value_alerts()
    # fixture 1 edge 0.04 (sotto 0.08) escluso
    # fixture 2 edge 0.09 incluso
    # fixture 3 edge 0.07 escluso
    # fixture 4 edge 0.12 incluso
    assert len(alerts) == 2
    f_ids = {a["fixture_id"] for a in alerts}
    assert f_ids == {2, 4}

    out = write_value_alerts(alerts)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["threshold_edge"] == 0.08
