import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def alerts_file(tmp_path: Path):
    out_dir = tmp_path / "value_alerts"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": 3,
        "alerts": [
            {
                "source": "prediction",
                "value_type": "prediction_value",
                "fixture_id": 10,
                "value_side": "home_win",
                "value_edge": 0.07,
            },
            {
                "source": "consensus",
                "value_type": "consensus_value",
                "fixture_id": 10,
                "value_side": "home_win",
                "value_edge": 0.05,
            },
            {
                "source": "prediction",
                "value_type": "prediction_value",
                "fixture_id": 11,
                "value_side": "away_win",
                "value_edge": 0.02,
            },
        ],
    }
    (out_dir / "value_alerts.json").write_text(json.dumps(payload), encoding="utf-8")
    return out_dir / "value_alerts.json"


def test_value_alerts_basic(client, alerts_file):
    r = client.get("/value_alerts")
    assert r.status_code == 200
    js = r.json()
    assert js["total_available"] == 3
    assert js["count"] == 3


def test_value_alerts_filter_source(client, alerts_file):
    r = client.get("/value_alerts?source=consensus")
    js = r.json()
    assert js["count"] == 1
    assert all(a["source"] == "consensus" for a in js["items"])


def test_value_alerts_min_edge(client, alerts_file):
    r = client.get("/value_alerts?min_edge=0.05")
    js = r.json()
    # 0.07 e 0.05 passano
    assert js["count"] == 2
    # Ordinati per edge desc
    assert js["items"][0]["value_edge"] >= js["items"][1]["value_edge"]


def test_value_alerts_not_found(client):
    r = client.get("/value_alerts")
    js = r.json()
    assert js["count"] == 0
    assert js["total_available"] == 0


def test_value_alerts_limit(client, alerts_file):
    r = client.get("/value_alerts?limit=2")
    js = r.json()
    assert js["count"] == 2
