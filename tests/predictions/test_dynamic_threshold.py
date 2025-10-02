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
    monkeypatch.setenv("VALUE_ALERT_MIN_EDGE", "0.05")
    monkeypatch.setenv("VALUE_ALERT_DYNAMIC_ENABLE", "1")
    monkeypatch.setenv("VALUE_ALERT_DYNAMIC_TARGET_COUNT", "2")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()

def _write_predictions(tmp_path: Path, edges):
    d = tmp_path / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    preds = []
    for i, e in enumerate(edges):
        preds.append({
            "fixture_id": 200 + i,
            "model_version": "baseline-v1",
            "value": {
                "active": True,
                "value_side": "home_win",
                "value_edge": e,
            }
        })
    (d / "latest_predictions.json").write_text(json.dumps({"predictions": preds}), encoding="utf-8")

def test_dynamic_threshold(tmp_path: Path):
    # 5 prediction value => > target => threshold sale (fattore > 1)
    _write_predictions(tmp_path, [0.06, 0.07, 0.08, 0.09, 0.10])
    alerts, eff_th = build_value_alerts()
    write_value_alerts((alerts, eff_th))
    assert eff_th >= 0.05
    payload = json.loads((tmp_path / "value_alerts" / "value_alerts.json").read_text(encoding="utf-8"))
    assert payload["dynamic_enabled"] is True
    assert payload["effective_threshold"] >= 0.05
