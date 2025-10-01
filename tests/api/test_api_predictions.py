import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    # Config minima
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_PREDICTIONS", "1")
    monkeypatch.setenv("ENABLE_PREDICTIONS_USE_ODDS", "1")
    monkeypatch.setenv("ENABLE_VALUE_DETECTION", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def predictions_file(tmp_path: Path):
    preds_dir = tmp_path / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_version": "baseline-v1",
        "count": 3,
        "enriched_with_odds": True,
        "value_detection": True,
        "predictions": [
            {
                "fixture_id": 10,
                "prob": {"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
                "odds": {
                    "odds_implied": {"home_win": 0.36, "draw": 0.32, "away_win": 0.32},
                    "odds_margin": 0.05,
                },
                "value": {
                    "active": True,
                    "value_side": "home_win",
                    "value_edge": 0.04,
                    "deltas": {"home_win": 0.04, "draw": -0.02, "away_win": -0.02},
                },
            },
            {
                "fixture_id": 11,
                "prob": {"home_win": 0.33, "draw": 0.34, "away_win": 0.33},
                "odds": {
                    "odds_implied": {"home_win": 0.33, "draw": 0.34, "away_win": 0.33},
                    "odds_margin": 0.02,
                },
                "value": {
                    "active": False,
                    "value_side": "home_win",
                    "value_edge": 0.0,
                    "deltas": {"home_win": 0.0, "draw": 0.0, "away_win": 0.0},
                },
            },
            {
                "fixture_id": 12,
                "prob": {"home_win": 0.5, "draw": 0.25, "away_win": 0.25},
                "odds": {
                    "odds_implied": {"home_win": 0.42, "draw": 0.30, "away_win": 0.28},
                    "odds_margin": 0.05,
                },
                "value": {
                    "active": True,
                    "value_side": "home_win",
                    "value_edge": 0.08,
                    "deltas": {"home_win": 0.08, "draw": -0.05, "away_win": -0.03},
                },
            },
        ],
    }
    (preds_dir / "latest_predictions.json").write_text(json.dumps(payload), encoding="utf-8")
    return preds_dir / "latest_predictions.json"


def test_predictions_basic(client, predictions_file):
    r = client.get("/predictions")
    assert r.status_code == 200
    js = r.json()
    assert js["total_available"] == 3
    assert js["count"] == 3
    assert js["value_filtered"] is False
    assert len(js["items"]) == 3


def test_predictions_value_only(client, predictions_file):
    r = client.get("/predictions?value_only=1")
    js = r.json()
    assert js["value_filtered"] is True
    # Due active (fixture_id 10 edge 0.04, fixture_id 12 edge 0.08)
    assert js["count"] == 2
    # Ordinati per edge desc => prima fixture_id 12
    assert js["items"][0]["fixture_id"] == 12
    assert js["items"][1]["fixture_id"] == 10


def test_predictions_min_edge(client, predictions_file):
    r = client.get("/predictions?min_edge=0.05")
    js = r.json()
    assert js["value_filtered"] is True
    # Solo fixture_id 12 ha edge 0.08 >= 0.05
    assert js["count"] == 1
    assert js["items"][0]["fixture_id"] == 12


def test_predictions_limit(client, predictions_file):
    r = client.get("/predictions?limit=2")
    js = r.json()
    assert js["count"] == 2
    assert len(js["items"]) == 2


def test_predictions_file_missing(client, tmp_path):
    # Nessun file creato
    r = client.get("/predictions")
    assert r.status_code == 200
    js = r.json()
    assert js["count"] == 0
    assert js["total_available"] == 0
    assert js["items"] == []
    assert "detail" in js
