import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.scoreboard import build_scoreboard, write_scoreboard
from core.config import _reset_settings_cache_for_tests


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    # Config minima per evitare errori
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_build_scoreboard_with_delta(tmp_path):
    now = datetime.now(timezone.utc)
    fixtures = [
        # LIVE fixture
        {
            "fixture_id": 1,
            "status": "1H",
            "date_utc": (now - timedelta(minutes=10)).isoformat(),
            "home_score": 1,
            "away_score": 0,
        },
        # Upcoming (entro 24h)
        {
            "fixture_id": 2,
            "status": "NS",
            "date_utc": (now + timedelta(hours=3)).isoformat(),
            "home_score": None,
            "away_score": None,
        },
        # Non upcoming (oltre 24h)
        {
            "fixture_id": 3,
            "status": "NS",
            "date_utc": (now + timedelta(hours=30)).isoformat(),
        },
        # Invalid date string (copre _parse_dt failure)
        {
            "fixture_id": 4,
            "status": "NS",
            "date_utc": "INVALID-DATE",
        },
    ]

    metrics = {
        "summary": {"total_new": 4},
        "change_breakdown": {"score_change": 2, "status_change": 1, "both": 0, "other": 0},
    }
    delta = {
        "added": [{"fixture_id": 10}],
        "removed": [],
        "modified": [{"fixture_id": 1}],
        "change_breakdown": {"score_change": 1, "status_change": 0, "both": 0, "other": 0},
    }

    sb = build_scoreboard(fixtures, metrics, delta, upcoming_window_hours=24, limit_lists=5)
    assert sb["total"] == 4
    assert sb["live_count"] == 1
    assert sb["upcoming_count_next_24h"] == 1
    assert sb["recent_delta"] == {"added": 1, "removed": 0, "modified": 1}
    assert sb["change_breakdown"] == {"score_change": 1, "status_change": 0, "both": 0, "other": 0}
    assert len(sb["live_fixtures"]) == 1
    assert len(sb["upcoming_next_24h"]) == 1
    assert sb["last_fetch_total_new"] == 4

    path = write_scoreboard(sb)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total"] == 4


def test_build_scoreboard_without_delta_fallback_metrics():
    # Nessun delta => recent_delta zero e change_breakdown preso da metrics
    fixtures = [
        {"fixture_id": 1, "status": "2H", "date_utc": datetime.now(timezone.utc).isoformat()},
        {"fixture_id": 2, "status": "NS", "date_utc": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()},
    ]
    metrics = {
        "summary": {"total_new": 2},
        "change_breakdown": {"score_change": 5, "status_change": 2, "both": 1, "other": 0},
    }
    sb = build_scoreboard(fixtures, metrics, delta=None)
    assert sb["recent_delta"] == {"added": 0, "removed": 0, "modified": 0}
    assert sb["change_breakdown"]["score_change"] == 5
    # upcoming_count_next_24h deve essere 1 (fixture_id 2)
    assert sb["upcoming_count_next_24h"] == 1
