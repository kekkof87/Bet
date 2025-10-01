import json
from pathlib import Path

import pytest

from core.config import _reset_settings_cache_for_tests
from notifications.dispatcher import load_alert_events, dispatch_alerts


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ALERTS_FILE", "1")
    monkeypatch.setenv("ENABLE_ALERT_DISPATCH", "1")
    monkeypatch.setenv("ALERT_DISPATCH_MODE", "stdout")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_load_and_dispatch(tmp_path: Path):
    alerts_dir = tmp_path / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    (alerts_dir / "last_alerts.json").write_text(
        json.dumps(
            {
                "generated_at": "2025-01-01T00:00:00Z",
                "count": 2,
                "events": [
                    {"type": "score_update", "fixture_id": 1, "old_score": "0-0", "new_score": "1-0", "status": "1H"},
                    {"type": "status_transition", "fixture_id": 2, "from": "NS", "to": "1H"},
                ],
            }
        ),
        encoding="utf-8",
    )
    events = load_alert_events()
    assert len(events) == 2
    sent = dispatch_alerts(events)
    assert sent == 2


def test_disabled_dispatch(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ENABLE_ALERT_DISPATCH", "0")
    _reset_settings_cache_for_tests()
    events = [{"type": "score_update", "fixture_id": 10}]
    sent = dispatch_alerts(events)
    assert sent == 0
