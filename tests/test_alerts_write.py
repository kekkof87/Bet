import json
from pathlib import Path

import pytest

from core.alerts import write_alerts
from core.config import _reset_settings_cache_for_tests


@pytest.fixture
def events_sample():
    return [
        {"type": "score_update", "fixture_id": 10, "old_score": "0-0", "new_score": "1-0", "status": "1H"},
        {"type": "status_transition", "fixture_id": 10, "from": "NS", "to": "1H"},
    ]


def test_write_alerts_disabled(monkeypatch, tmp_path, events_sample):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ALERTS_FILE", "0")
    _reset_settings_cache_for_tests()
    result = write_alerts(events_sample)
    assert result is None


def test_write_alerts_enabled(monkeypatch, tmp_path, events_sample):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ALERTS_FILE", "1")
    _reset_settings_cache_for_tests()
    path = write_alerts(events_sample)
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert len(data["events"]) == 2
