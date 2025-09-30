from __future__ import annotations

import re
from typing import Any, Dict, Optional
from core.logging import get_logger

logger = get_logger("core.normalization")

# Pattern ISO 8601 semplice: YYYY-MM-DDTHH:MM:SS (accetta suffisso Z o offset)
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)

_warned_invalid_date = False  # run-level (non thread-safe, sufficiente qui)


def _validate_date(value: Optional[str]) -> tuple[Optional[str], bool]:
    if not value:
        return value, False
    if _ISO_DATETIME_RE.match(value):
        return value, True
    global _warned_invalid_date
    if not _warned_invalid_date:
        logger.warning("Rilevata date_utc non conforme ISO8601 (prima occorrenza): %s", value)
        _warned_invalid_date = True
    return value, False


def normalize_api_football_fixture(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizza record grezzo dell'API-Football.
    Aggiunge campo 'valid_date_utc' boolean.
    """
    fixture = item.get("fixture", {}) or {}
    league = item.get("league", {}) or {}
    teams = item.get("teams", {}) or {}
    goals = item.get("goals", {}) or {}

    def _as_int(v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    date_raw = fixture.get("date")
    date_norm, valid = _validate_date(date_raw)

    return {
        "fixture_id": _as_int(fixture.get("id")),
        "league_id": _as_int(league.get("id")),
        "season": _as_int(league.get("season")),
        "date_utc": date_norm,
        "valid_date_utc": valid,
        "home_team": (teams.get("home") or {}).get("name"),
        "away_team": (teams.get("away") or {}).get("name"),
        "status": ((fixture.get("status") or {}) or {}).get("short"),
        "home_score": _as_int(goals.get("home")),
        "away_score": _as_int(goals.get("away")),
        "provider": "api_football",
    }


__all__ = ["normalize_api_football_fixture"]
