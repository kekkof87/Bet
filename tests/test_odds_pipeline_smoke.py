from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from odds.pipeline import run_odds_pipeline


def test_odds_pipeline_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ODDS_INGESTION", "1")
    monkeypatch.setenv("ODDS_PROVIDER", "stub")

    fixtures: List[Dict[str, Any]] = [
        {
            "fixture_id": 123,
            "league_id": "PL",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "status": "NS",
        }
    ]
    out = run_odds_pipeline(fixtures, provider_name="stub")
    assert out is not None
    assert out.name == "odds_latest.json"
    payload = (tmp_path / "odds" / "odds_latest.json").read_text(encoding="utf-8")
    assert '"entries"' in payload
