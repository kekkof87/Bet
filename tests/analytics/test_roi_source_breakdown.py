import json
from pathlib import Path
import pytest

from analytics.roi import build_or_update_roi
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("ENABLE_ROI_TIMELINE", "0")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_alerts(tmp_path: Path):
    alerts_dir = tmp_path / "value_alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    # 2 prediction + 1 consensus (solo quelle NS verranno convertite in picks)
    (alerts_dir / "value_alerts.json").write_text(
        json.dumps(
            {
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
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 11,
                        "value_side": "draw",
                        "value_edge": 0.06,
                    },
                    {
                        "source": "consensus",
                        "value_type": "consensus_value",
                        "fixture_id": 12,
                        "value_side": "away_win",
                        "value_edge": 0.08,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_source_breakdown(tmp_path: Path):
    _write_alerts(tmp_path)
    fixtures = [
        {"fixture_id": 10, "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 11, "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 12, "status": "NS", "home_score": 0, "away_score": 0},
    ]
    build_or_update_roi(fixtures)

    roi_dir = tmp_path / "roi"
    metrics_path = roi_dir / "roi_metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["picks_prediction"] == 2
    assert metrics["picks_consensus"] == 1
    assert metrics["settled_prediction"] == 0
    assert metrics["profit_units_prediction"] == 0.0
    assert "yield_prediction" in metrics
    assert "yield_consensus" in metrics
