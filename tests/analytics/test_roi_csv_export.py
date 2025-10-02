from pathlib import Path
import json
import csv
import pytest

from analytics.roi import build_or_update_roi
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    monkeypatch.setenv("ENABLE_ROI_CSV_EXPORT", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _write_value_alerts(tmp_path: Path):
    d = tmp_path / "value_alerts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "value_alerts.json").write_text(
        json.dumps(
            {
                "count": 2,
                "alerts": [
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 501,
                        "value_side": "home_win",
                        "value_edge": 0.06,
                    },
                    {
                        "source": "prediction",
                        "value_type": "prediction_value",
                        "fixture_id": 502,
                        "value_side": "away_win",
                        "value_edge": 0.07,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_roi_csv_export(tmp_path: Path):
    _write_value_alerts(tmp_path)
    fixtures = [
        {"fixture_id": 501, "status": "NS", "home_score": 0, "away_score": 0},
        {"fixture_id": 502, "status": "NS", "home_score": 0, "away_score": 0},
    ]
    build_or_update_roi(fixtures)

    roi_dir = tmp_path / "roi"
    csv_file = roi_dir / "roi_export.csv"
    assert csv_file.exists()

    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    for r in rows:
        assert "fixture_id" in r
        assert "source" in r
        assert "stake" in r
        assert "profit_contribution" in r
