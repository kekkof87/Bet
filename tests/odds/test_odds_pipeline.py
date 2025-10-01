import json
from pathlib import Path

import pytest

from odds.pipeline import run_odds_pipeline
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ODDS_INGESTION", "1")
    monkeypatch.setenv("ODDS_PROVIDER", "stub")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_odds_pipeline_basic(tmp_path):
    fixtures = [
        {
            "fixture_id": 10,
            "home_team": "A",
            "away_team": "B",
            "home_score": 0,
            "away_score": 0,
            "status": "NS",
        },
        {
            "fixture_id": 11,
            "home_team": "C",
            "away_team": "D",
            "home_score": 1,
            "away_score": 0,
            "status": "1H",
        },
    ]
    path = run_odds_pipeline(fixtures)
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert len(data["entries"]) == 2
    sample = data["entries"][0]
    assert "fixture_id" in sample and "market" in sample
    market = sample["market"]
    assert {"home_win", "draw", "away_win"}.issubset(market.keys())


def test_odds_pipeline_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_ODDS_INGESTION", "0")
    _reset_settings_cache_for_tests()
    fixtures = [{"fixture_id": 99}]
    path = run_odds_pipeline(fixtures)
    assert path is None
