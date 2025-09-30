from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FixtureRecord:
    fixture_id: Optional[int]
    league_id: Optional[int]
    season: Optional[int]
    date_utc: Optional[str]
    home_team: Optional[str]
    away_team: Optional[str]
    status: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
    provider: str = "api_football"

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> "FixtureRecord":
        # raw è nel formato normalizzato dal provider (fixture, league, teams, goals)
        fixture = raw.get("fixture", {})
        league = raw.get("league", {})
        teams = raw.get("teams", {})
        goals = raw.get("goals", {})

        def _as_int(v):
            try:
                return int(v) if v is not None else None
            except (ValueError, TypeError):
                return None

        return cls(
            fixture_id=_as_int(fixture.get("id")),
            league_id=_as_int(league.get("id")),
            season=_as_int(league.get("season")),
            date_utc=fixture.get("date"),
            home_team=teams.get("home", {}).get("name"),
            away_team=teams.get("away", {}).get("name"),
            status=(fixture.get("status") or {}).get("short"),
            home_score=_as_int(goals.get("home")),
            away_score=_as_int(goals.get("away")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "league_id": self.league_id,
            "season": self.season,
            "date_utc": self.date_utc,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "status": self.status,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "provider": self.provider,
        }
