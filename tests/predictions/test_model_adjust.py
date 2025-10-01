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
    monkeypatch.setenv("ENABLE_MODEL_ADJUST", "1")
    monkeypatch.setenv("MODEL_ADJUST_WEIGHT", "0.6")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_model_adjust_block(tmp_path: Path):
    fixtures = [
        {"fixture_id": 500, "home_team": "H", "away_team": "A", "status": "NS", "home_score": 0, "away_score": 0},
    ]

    odds_dir = tmp_path / "odds"
    odds_dir.mkdir(parents=True, exist_ok=True)
    (odds_dir / "odds_latest.json").write_text(
        json.dumps(
            {
                "provider": "stub",
                "count": 1,
                "entries": [
                    {
                        "fixture_id": 500,
                        "source": "stub-book",
                        "fetched_at": "2025-01-01T00:00:00Z",
                        "market": {
                            "home_win": 2.5,  # implied ~0.40
                            "draw": 3.6,      # ~0.2777
                            "away_win": 3.0,  # ~0.3333
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
    pred = data["predictions"][0]
    assert data["model_adjust_enabled"] is True
    assert "prob_adjusted" in pred
    pa = pred["prob_adjusted"]
    assert abs(sum(pa.values()) - 1.0) < 1e-9
    # Deve esserci differenza rispetto al prob originale se odds diverse
    if "prob" in pred:
        diffs = sum(abs(pred["prob"][k] - pa[k]) for k in pa)
        assert diffs > 0
