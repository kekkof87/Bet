import json
from pathlib import Path
import pytest

from core.config import _reset_settings_cache_for_tests
from predictions.value_alerts import build_value_alerts, write_value_alerts


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    """
    Abilita value alerts e imposta una soglia VALUE_ALERT_MIN_EDGE più bassa (0.03)
    per mantenere il comportamento atteso dal test originale:
    - prediction fixture 1 (edge 0.05) -> incluso
    - consensus fixture 1 (edge 0.03) -> incluso
    Senza questo override, con la nuova introduzione di VALUE_ALERT_MIN_EDGE (default=VALUE_MIN_EDGE=0.05)
    l'alert consensus (0.03) verrebbe escluso e il test fallirebbe.
    """
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    # Override nuova soglia per permettere consensus edge 0.03
    monkeypatch.setenv("VALUE_ALERT_MIN_EDGE", "0.03")
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
    # Due attivi: prediction fixture 1 + consensus fixture 1
    assert len(alerts) == 2
    # Ordine non garantito, controlliamo insiemi
    sources = {a["source"] for a in alerts}
    assert sources == {"prediction", "consensus"}
    fixture_ids = {a["fixture_id"] for a in alerts}
    assert fixture_ids == {1}

    out = write_value_alerts(alerts)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 2
    # Soglia riportata nel file deve riflettere l'override fixture
    assert abs(payload["threshold_edge"] - 0.03) < 1e-9
