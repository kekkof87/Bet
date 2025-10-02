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
    monkeypatch.setenv("ENABLE_ROI_TIMELINE", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_alerts(tmp_path: Path, fixture_id: int, edge: float, status: str):
    alerts_dir = tmp_path / "value_alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    (alerts_dir / "value_alerts.json").write_text(
        json.dumps(
            {
                "count": 1,
                "alerts": [
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": fixture_id,
                        "value_side": "home_win",
                        "value_edge": edge,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_roi_timeline_append(tmp_path: Path):
    # Step 1: fixture NS genera pick
    fixtures = [
        {"fixture_id": 10, "home_team": "A", "away_team": "B", "home_score": 0, "away_score": 0, "status": "NS"},
    ]
    _write_alerts(tmp_path, 10, 0.06, "NS")
    build_or_update_roi(fixtures)

    roi_dir = tmp_path / "roi"
    history_file = roi_dir / "roi_history.jsonl"
    daily_file = roi_dir / "roi_daily.json"
    assert history_file.exists()
    assert daily_file.exists()

    hist_lines = [ln for ln in history_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines) == 1
    first = json.loads(hist_lines[0])
    assert "total_picks" in first

    daily = json.loads(daily_file.read_text(encoding="utf-8"))
    assert isinstance(daily, dict)
    assert len(daily) == 1
    # Step 2: fixture FT -> settlement -> seconda riga timeline
    fixtures[0]["status"] = "FT"
    fixtures[0]["home_score"] = 1
    fixtures[0]["away_score"] = 0
    build_or_update_roi(fixtures)
    hist_lines2 = [ln for ln in history_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(hist_lines2) == 2
