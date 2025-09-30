import json
import pytest

from core.metrics import write_metrics_snapshot, write_last_delta_event
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_write_metrics_snapshot(monkeypatch, tmp_path):
    payload = {"summary": {"added": 1}, "fetch_stats": {"attempts": 1}}
    out = write_metrics_snapshot(payload)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["added"] == 1


def test_write_last_delta_event(monkeypatch, tmp_path):
    delta = {"added": [{"fixture_id": 10}], "removed": [], "modified": []}
    out = write_last_delta_event(delta)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["added"][0]["fixture_id"] == 10


def test_disable_metrics_events(monkeypatch):
    monkeypatch.setenv("ENABLE_METRICS_FILE", "false")
    monkeypatch.setenv("ENABLE_EVENTS_FILE", "false")
    _reset_settings_cache_for_tests()

    payload = {"summary": {}}
    metrics_path = write_metrics_snapshot(payload)
    events_path = write_last_delta_event({"added": [], "removed": [], "modified": []})
    assert not metrics_path.exists()
    assert not events_path.exists()
