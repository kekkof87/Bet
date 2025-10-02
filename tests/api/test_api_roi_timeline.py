import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_ROI_TIMELINE", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    return TestClient(create_app())


def _write_timeline(tmp_path: Path):
    roi_dir = tmp_path / "roi"
    roi_dir.mkdir(parents=True, exist_ok=True)
    history = [
        {"ts": "2025-10-01T10:00:00Z", "total_picks": 5, "settled_picks": 3, "profit_units": 1.0, "yield": 0.1, "hit_rate": 0.6},
        {"ts": "2025-10-01T11:00:00Z", "total_picks": 6, "settled_picks": 4, "profit_units": 1.2, "yield": 0.1, "hit_rate": 0.5},
        {"ts": "2025-10-02T09:30:00Z", "total_picks": 7, "settled_picks": 5, "profit_units": 1.5, "yield": 0.11, "hit_rate": 0.57},
    ]
    with (roi_dir / "roi_history.jsonl").open("w", encoding="utf-8") as f:
        for r in history:
            f.write(json.dumps(r) + "\n")
    (roi_dir / "roi_daily.json").write_text(
        json.dumps(
            {
                "2025-10-01": {
                    "last_ts": "2025-10-01T11:00:00Z",
                    "runs": 2,
                    "total_picks": 6,
                    "settled_picks": 4,
                    "profit_units": 1.2,
                    "yield": 0.1,
                    "hit_rate": 0.5,
                },
                "2025-10-02": {
                    "last_ts": "2025-10-02T09:30:00Z",
                    "runs": 1,
                    "total_picks": 7,
                    "settled_picks": 5,
                    "profit_units": 1.5,
                    "yield": 0.11,
                    "hit_rate": 0.57,
                },
            }
        ),
        encoding="utf-8",
    )


def test_timeline_full(client, tmp_path: Path):
    _write_timeline(tmp_path)
    r = client.get("/roi/timeline?mode=full&limit=10")
    assert r.status_code == 200
    js = r.json()
    assert js["included"]["timeline"] is True
    assert js["included"]["daily"] is False
    assert js["count"] == 3
    assert len(js["items"]) == 3


def test_timeline_daily_only(client, tmp_path: Path):
    _write_timeline(tmp_path)
    r = client.get("/roi/timeline?mode=daily")
    assert r.status_code == 200
    js = r.json()
    assert js["included"]["daily"] is True
    assert js["included"]["timeline"] is False
    assert "2025-10-01" in js["daily"]


def test_timeline_filtered(client, tmp_path: Path):
    _write_timeline(tmp_path)
    r = client.get("/roi/timeline?mode=both&start_date=2025-10-02")
    assert r.status_code == 200
    js = r.json()
    # timeline solo record >= 2025-10-02
    assert js["count"] == 1
    assert len(js["items"]) == 1
    assert js["items"][0]["ts"].startswith("2025-10-02")
    # daily solo 2025-10-02
    assert list(js["daily"].keys()) == ["2025-10-02"]


def test_timeline_bad_date(client, tmp_path: Path):
    _write_timeline(tmp_path)
    r = client.get("/roi/timeline?start_date=2025-13-01")
    assert r.status_code == 400
