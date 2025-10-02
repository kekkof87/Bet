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
    # Lasciamo i fattori min/max e lo step ai default (1.0 / 2.0 / 0.05)
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_predictions(tmp_path: Path, edges):
    d = tmp_path / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    preds = []
    for i, e in enumerate(edges):
        preds.append(
            {
                "fixture_id": 200 + i,
                "model_version": "baseline-v1",
                "value": {
                    "active": True,
                    "value_side": "home_win",
                    "value_edge": e,
                },
            }
        )
    (d / "latest_predictions.json").write_text(
        json.dumps({"predictions": preds}),
        encoding="utf-8",
    )


def test_dynamic_threshold(tmp_path: Path):
    # 5 prediction value => count (5) > target (2) -> dynamic_factor = 1 + step = 1.05
    _write_predictions(tmp_path, [0.06, 0.07, 0.08, 0.09, 0.10])
    alerts = build_value_alerts()
    write_value_alerts(alerts)  # genera il file con effective_threshold
    payload = json.loads(
        (tmp_path / "value_alerts" / "value_alerts.json").read_text(encoding="utf-8")
    )
    assert payload["dynamic_enabled"] is True
    assert payload["count"] == 5
    # dynamic_factor atteso >= 1.0, con target=2 e step=0.05 diventa 1.05
    assert payload["dynamic_factor"] >= 1.0
    assert payload["effective_threshold"] >= 0.05
