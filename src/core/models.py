from __future__ import annotations

from typing import List, Optional, TypedDict


class FixtureRecord(TypedDict, total=False):
    fixture_id: int
    league_id: int
    season: int
    home_team: str
    away_team: str
    kickoff_utc: str  # ISO 8601
    status: str
    home_score: Optional[int]
    away_score: Optional[int]
    odds_home: Optional[float]
    odds_draw: Optional[float]
    odds_away: Optional[float]


FixtureDataset = List[FixtureRecord]
