import json
from pathlib import Path
import pytest

from core.config import _reset_settings_cache_for_tests
from predictions.value_alerts import build_value_alerts, write_value_alerts
from analytics.roi import build_or_update_roi


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    # Abilitiamo merged alerts + ROI tracking per verificare pick 'merged'
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("ENABLE_MERGED_VALUE_ALERTS", "1")
    monkeypatch.setenv("MERGED_VALUE_EDGE_POLICY", "avg")
    monkeypatch.setenv("ROI_INCLUDE_MERGED", "1")
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    # Soglia comune
    monkeypatch.setenv("VALUE_ALERT_MIN_EDGE", "0.05")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_predictions(tmp_path: Path):
    d = tmp_path / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    (d / "latest_predictions.json").write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "fixture_id": 900,
                        "model_version": "baseline-v1",
                        "prob": {"home_win": 0.45, "draw": 0.3, "away_win": 0.25},
                        "value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.06,
                            "deltas": {"home_win": 0.06},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_consensus(tmp_path: Path):
    d = tmp_path / "consensus"
    d.mkdir(parents=True, exist_ok=True)
    (d / "consensus.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "fixture_id": 900,
                        "blended_prob": {"home_win": 0.47, "draw": 0.3, "away_win": 0.23},
                        "consensus_value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.09,
                            "deltas": {"home_win": 0.09},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_merged_alert_creation_and_roi_pick(tmp_path: Path):
    _write_predictions(tmp_path)
    _write_consensus(tmp_path)

    alerts = build_value_alerts()
    # Devono esserci 3 alert: prediction, consensus, merged
    assert len(alerts) == 3
    sources = {a["source"] for a in alerts}
    assert sources == {"prediction", "consensus", "merged"}

    merged = [a for a in alerts if a["source"] == "merged"][0]
    assert merged["value_type"] == "merged_value"
    # edge merged = avg(0.06,0.09)=0.075
    assert abs(merged["value_edge"] - 0.075) < 1e-9
    comps = merged["components"]
    assert comps["policy"] == "avg"

    out = write_value_alerts(alerts)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["merged_enabled"] is True
    assert payload["merged_policy"] == "avg"

    # Verifica ROI pick 'merged'
    fixtures = [
        {"fixture_id": 900, "status": "NS", "home_score": 0, "away_score": 0},
    ]
    build_or_update_roi(fixtures)
    ledger_path = tmp_path / "roi" / "ledger.json"
    assert ledger_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    # Dovrebbero apparire 3 picks (prediction, consensus, merged) se ROI_INCLUDE_CONSENSUS=default True e ROI_INCLUDE_MERGED=1
    sources_in_ledger = {p["source"] for p in ledger}
    assert "merged" in sources_in_ledger
    assert "prediction" in sources_in_ledger
    assert "consensus" in sources_in_ledger
