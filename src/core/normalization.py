from __future__ import annotations

from typing import Any, Dict


def normalize_api_football_fixture(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizza un record grezzo dell'API-Football (struttura 'fixture','league','teams','goals')
    in un dizionario coerente con FixtureRecord.to_dict().
    Campi mancanti o strutture inattese vengono degradate a None.
    """
    fixture = item.get("fixture", {}) or {}
    league = item.get("league", {}) or {}
    teams = item.get("teams", {}) or {}
    goals = item.get("goals", {}) or {}

    def _as_int(v: Any):
        try:
            return int(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    return {
        "fixture_id": _as_int(fixture.get("id")),
        "league_id": _as_int(league.get("id")),
        "season": _as_int(league.get("season")),
        "date_utc": fixture.get("date"),
        "home_team": (teams.get("home") or {}).get("name"),
        "away_team": (teams.get("away") or {}).get("name"),
        "status": ((fixture.get("status") or {}) or {}).get("short"),
        "home_score": _as_int(goals.get("home")),
        "away_score": _as_int(goals.get("away")),
        "provider": "api_football",
    }


__all__ = ["normalize_api_football_fixture"]
