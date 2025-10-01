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
    monkeypatch.setenv("CONSENSUS_BASELINE_WEIGHT", "0.5")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_consensus_blending(tmp_path: Path):
    # Predizioni baseline con odds implied
    preds_dir = tmp_path / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_version": "baseline-v1",
        "count": 2,
        "enriched_with_odds": True,
        "predictions": [
            {
                "fixture_id": 100,
                "model_version": "baseline-v1",
                "prob": {"home_win": 0.50, "draw": 0.30, "away_win": 0.20},
                "odds": {
                    "odds_implied": {"home_win": 0.42, "draw": 0.30, "away_win": 0.28},
                    "odds_margin": 0.05,
                },
            },
            {
                "fixture_id": 101,
                "model_version": "baseline-v1",
                "prob": {"home_win": 0.33, "draw": 0.34, "away_win": 0.33},
                # Nessun odds block: dovrebbe usare baseline puro
            },
        ],
    }
    (preds_dir / "latest_predictions.json").write_text(json.dumps(payload), encoding="utf-8")

    out = run_consensus_pipeline()
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["count"] == 2
    # Entry fixture 100 blended: media 0.5/0.42=0.46, 0.30/0.30=0.30, 0.20/0.28=0.24 (normalizza già)
    e100 = next(e for e in data["entries"] if e["fixture_id"] == 100)
    b = e100["blended_prob"]
    s = round(b["home_win"] + b["draw"] + b["away_win"], 6)
    assert abs(s - 1.0) < 1e-6
    # Home blended deve essere vicino a 0.46 (tolleranza)
    assert 0.455 <= b["home_win"] <= 0.465
    # Consenso valore presente
    assert "consensus_value" in e100

    e101 = next(e for e in data["entries"] if e["fixture_id"] == 101)
    # Nessun odds => blended == baseline (entro tolleranza)
    assert abs(e101["blended_prob"]["home_win"] - 0.33) < 1e-9
    assert "consensus_value" not in e101
