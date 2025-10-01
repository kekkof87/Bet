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
    monkeypatch.setenv("ENABLE_VALUE_DETECTION", "1")
    monkeypatch.setenv("VALUE_MIN_EDGE", "0.01")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_value_detection_block(tmp_path: Path):
    fixtures = [
        {"fixture_id": 200, "home_team": "X", "away_team": "Y", "status": "NS", "home_score": 0, "away_score": 0},
    ]

    odds_dir = tmp_path / "odds"
    odds_dir.mkdir(parents=True, exist_ok=True)
    # Impostiamo odds che creino una differenza evidente
    (odds_dir / "odds_latest.json").write_text(
        json.dumps(
            {
                "provider": "stub",
                "count": 1,
                "entries": [
                    {
                        "fixture_id": 200,
                        "source": "stub-book",
                        "fetched_at": "2025-01-01T00:00:00Z",
                        "market": {
                            "home_win": 2.5,  # implied ~0.40
                            "draw": 3.6,      # ~0.2777
                            "away_win": 3.0,  # ~0.3333  (sum raw ~1.011)
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run_baseline_predictions(fixtures)
    out_file = tmp_path / "predictions" / "latest_predictions.json"
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["value_detection"] is True
    pred = data["predictions"][0]
    assert "value" in pred
    vb = pred["value"]
    assert "value_side" in vb
    assert "value_edge" in vb
    assert "deltas" in vb
    assert isinstance(vb["deltas"], dict)
