import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fixtures_empty(client):
    r = client.get("/fixtures")
    assert r.status_code == 200
    assert r.json() == []


def test_scoreboard_not_found(client):
    r = client.get("/scoreboard")
    assert r.status_code == 404


def test_metrics_delta_scoreboard(client, tmp_path):
    # Prepara file metrics + delta + scoreboard
    data_dir = Path(tmp_path)
    (data_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (data_dir / "events").mkdir(parents=True, exist_ok=True)

    metrics_payload = {
        "summary": {"added": 1, "removed": 0, "modified": 2, "total_new": 10},
        "change_breakdown": {"score_change": 1, "status_change": 1, "both": 0, "other": 0},
        "fetch_stats": {"attempts": 1, "retries": 0, "latency_ms": 12.3, "last_status": 200},
        "total_fixtures": 10,
    }
    (data_dir / "metrics" / "last_run.json").write_text(json.dumps(metrics_payload), encoding="utf-8")

    delta_payload = {
        "added": [{"fixture_id": 1}],
        "removed": [],
        "modified": [],
        "change_breakdown": {"score_change": 1, "status_change": 0, "both": 0, "other": 0},
    }
    (data_dir / "events" / "last_delta.json").write_text(json.dumps(delta_payload), encoding="utf-8")

    scoreboard_payload = {
        "generated_at": "2025-09-30T12:00:00Z",
        "total": 10,
        "live_count": 0,
        "upcoming_count_next_24h": 0,
        "recent_delta": {"added": 1, "removed": 0, "modified": 0},
        "change_breakdown": {"score_change": 1, "status_change": 0, "both": 0, "other": 0},
        "live_fixtures": [],
        "upcoming_next_24h": [],
        "last_fetch_total_new": 10,
    }
    (data_dir / "scoreboard.json").write_text(json.dumps(scoreboard_payload), encoding="utf-8")

    # /delta
    r_delta = client.get("/delta")
    assert r_delta.status_code == 200
    assert r_delta.json()["summary"]["total_new"] == 10

    # /metrics
    r_metrics = client.get("/metrics")
    assert r_metrics.status_code == 200
    assert r_metrics.json()["fetch_stats"]["attempts"] == 1

    # /scoreboard
    r_sb = client.get("/scoreboard")
    assert r_sb.status_code == 200
    assert r_sb.json()["total"] == 10
