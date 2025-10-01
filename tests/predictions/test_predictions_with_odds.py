import json
from pathlib import Path

import pytest

from predictions.pipeline import run_baseline_predictions
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_PREDICTIONS", "1")
    monkeypatch.setenv("ENABLE_PREDICTIONS_USE_ODDS", "1")
    monkeypatch.setenv("ENABLE_ODDS_INGESTION", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_predictions_with_odds_enrichment(tmp_path: Path):
    # Fixtures di test
    fixtures = [
        {"fixture_id": 100, "home_team": "A", "away_team": "B", "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 101, "home_team": "C", "away_team": "D", "status": "1H", "home_score": 1, "away_score": 0},
    ]

    # Odds file fittizio
    odds_dir = tmp_path / "odds"
    odds_dir.mkdir(parents=True, exist_ok=True)
    (odds_dir / "odds_latest.json").write_text(
        json.dumps(
            {
                "provider": "stub",
                "count": 2,
                "entries": [
                    {
                        "fixture_id": 100,
                        "source": "stub-book",
                        "fetched_at": "2025-01-01T00:00:00Z",
                        "market": {"home_win": 2.1, "draw": 3.4, "away_win": 3.2},
                    },
                    {
                        "fixture_id": 101,
                        "source": "stub-book",
                        "fetched_at": "2025-01-01T00:00:05Z",
                        "market": {"home_win": 1.9, "draw": 3.5, "away_win": 4.0},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    run_baseline_predictions(fixtures)

    out_file = tmp_path / "predictions" / "latest_predictions.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert data["enriched_with_odds"] is True
    for entry in data["predictions"]:
        assert "prob" in entry
        assert "fixture_id" in entry
        assert "odds" in entry
        o = entry["odds"]
        assert "odds_original" in o
        assert "odds_implied" in o
        assert "odds_margin" in o
        # Somma implied vicina a 1
        s = sum(o["odds_implied"].values())
        assert abs(s - 1.0) < 1e-6
