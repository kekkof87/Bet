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
    monkeypatch.setenv("ENABLE_VALUE_ALERTS", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


@pytest.fixture
def client():
    return TestClient(create_app())


def test_roi_endpoint_basic(client, tmp_path: Path):
    # Prepara ledger + metrics
    roi_dir = tmp_path / "roi"
    roi_dir.mkdir(parents=True, exist_ok=True)
    (roi_dir / "ledger.json").write_text(
        json.dumps(
            [
                {
                    "fixture_id": 10,
                    "source": "prediction",
                    "side": "home_win",
                    "edge": 0.06,
                    "stake": 1.0,
                    "decimal_odds": 2.1,
                    "settled": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    (roi_dir / "roi_metrics.json").write_text(
        json.dumps(
            {
                "generated_at": "2025-01-01T00:00:00Z",
                "total_picks": 1,
                "settled_picks": 0,
                "open_picks": 1,
                "wins": 0,
                "losses": 0,
                "profit_units": 0.0,
                "yield": 0.0,
                "hit_rate": 0.0,
            }
        ),
        encoding="utf-8",
    )

    r = client.get("/roi")
    assert r.status_code == 200
    js = r.json()
    assert js["metrics"]["total_picks"] == 1
    assert js["detail_included"] is False

    r2 = client.get("/roi?detail=1")
    js2 = r2.json()
    assert js2["detail_included"] is True
    assert len(js2["items"]) == 1


def test_roi_endpoint_filters(client, tmp_path: Path):
    roi_dir = tmp_path / "roi"
    roi_dir.mkdir(parents=True, exist_ok=True)
    ledger = [
        {
            "fixture_id": 10,
            "source": "prediction",
            "side": "home_win",
            "edge": 0.06,
            "stake": 1.0,
            "decimal_odds": 2.1,
            "settled": False,
        },
        {
            "fixture_id": 11,
            "source": "consensus",
            "side": "draw",
            "edge": 0.04,
            "stake": 1.0,
            "decimal_odds": 3.3,
            "settled": True,
            "result": "loss",
        },
    ]
    (roi_dir / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    (roi_dir / "roi_metrics.json").write_text(
        json.dumps(
            {
                "generated_at": "2025-01-01T00:00:00Z",
                "total_picks": 2,
                "settled_picks": 1,
                "open_picks": 1,
                "wins": 0,
                "losses": 1,
                "profit_units": -1.0,
                "yield": -0.5,
                "hit_rate": 0.0,
            }
        ),
        encoding="utf-8",
    )

    r = client.get("/roi?detail=1&source=prediction")
    js = r.json()
    assert js["count"] if "count" in js else True  # compat
    assert len(js["items"]) == 1
    assert js["items"][0]["source"] == "prediction"

    r2 = client.get("/roi?detail=1&open_only=1")
    js2 = r2.json()
    assert len(js2["items"]) == 1
    assert js2["items"][0]["settled"] is False
