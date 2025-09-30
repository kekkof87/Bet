import json
import pytest

from predictions.pipeline import run_baseline_predictions
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_PREDICTIONS", "1")
    monkeypatch.setenv("MODEL_BASELINE_VERSION", "baseline-v1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_run_baseline_predictions(tmp_path):
    fixtures = [
        {
            "fixture_id": 100,
            "home_team": "Home",
            "away_team": "Away",
            "home_score": 0,
            "away_score": 0,
            "status": "NS",
            "date_utc": "2030-01-01T12:00:00Z",
        },
        {
            "fixture_id": 101,
            "home_team": "A",
            "away_team": "B",
            "home_score": 1,
            "away_score": 0,
            "status": "1H",
            "date_utc": "2030-01-01T11:00:00Z",
        },
    ]
    path = run_baseline_predictions(fixtures)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["model_version"] == "baseline-v1"
    assert data["count"] == 2
    pmap = {p["fixture_id"]: p for p in data["predictions"]}
    assert 100 in pmap and 101 in pmap
    for p in data["predictions"]:
        probs = p["prob"]
        total = round(probs["home_win"] + probs["draw"] + probs["away_win"], 5)
        assert total == 1.0
