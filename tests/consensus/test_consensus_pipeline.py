import json
from pathlib import Path
import pytest

from consensus.pipeline import run_consensus_pipeline
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_PREDICTIONS", "1")
    monkeypatch.setenv("ENABLE_CONSENSUS", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_consensus_pipeline(tmp_path):
    data_dir = Path(tmp_path)
    pred_dir = data_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_version": "baseline-v1",
        "count": 2,
        "predictions": [
            {
                "fixture_id": 10,
                "prob": {"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
                "model_version": "baseline-v1",
            },
            {
                "fixture_id": 11,
                "prob": {"home_win": 0.25, "draw": 0.25, "away_win": 0.5},
                "model_version": "baseline-v1",
            },
        ],
    }
    (pred_dir / "latest_predictions.json").write_text(json.dumps(payload), encoding="utf-8")
    path = run_consensus_pipeline()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert "entries" in data
    entry_map = {e["fixture_id"]: e for e in data["entries"]}
    assert entry_map[10]["consensus_confidence"] == 0.4
    assert round(entry_map[10]["ranking_score"], 4) == 0.1  # 0.4 - 0.3
    assert entry_map[11]["consensus_confidence"] == 0.5
    assert round(entry_map[11]["ranking_score"], 4) == -0.25  # 0.25 - 0.5
