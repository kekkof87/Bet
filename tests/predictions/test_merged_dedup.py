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
    monkeypatch.setenv("ENABLE_MERGED_VALUE_ALERTS", "1")
    monkeypatch.setenv("MERGED_VALUE_EDGE_POLICY", "max")
    monkeypatch.setenv("MERGED_DEDUP_ENABLE", "1")
    monkeypatch.setenv("VALUE_ALERT_MIN_EDGE", "0.05")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_pred_cons(tmp_path: Path):
    pdir = tmp_path / "predictions"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "latest_predictions.json").write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "fixture_id": 999,
                        "model_version": "v1",
                        "value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.07,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cdir = tmp_path / "consensus"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "consensus.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "fixture_id": 999,
                        "consensus_value": {
                            "active": True,
                            "value_side": "home_win",
                            "value_edge": 0.10,
                        },
                        "blended_prob": {"home_win": 0.5},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_dedup(tmp_path: Path):
    _write_pred_cons(tmp_path)
    alerts = build_value_alerts()
    write_value_alerts(alerts)
    sources = {a["source"] for a in alerts}
    # Con dedup attivo deve restare solo merged
    assert sources == {"merged"}
    assert len(alerts) == 1
    merged = alerts[0]
    assert merged["value_type"] == "merged_value"
