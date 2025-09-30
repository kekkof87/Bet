from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger
from .base import FixturesProviderBase
from .client import ApiFootballClient

logger = get_logger(__name__)


class ApiFootballFixturesProvider(FixturesProviderBase):
    """
    Provider che interroga l'endpoint /fixtures dell'API Football e normalizza
    la risposta in un dizionario coerente con il resto del sistema.
    """

    def __init__(self, client: Optional[ApiFootballClient] = None) -> None:
        self._client = client or ApiFootballClient()

    def fetch_fixtures(
        self,
        date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        settings = get_settings()
        if league_id is None:
            league_id = settings.default_league_id
        if season is None:
            season = settings.default_season

        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season

        raw = self._client.get("/fixtures", params=params or None)
        response = raw.get("response", [])
        if not isinstance(response, list):
            logger.warning("Formato inatteso: 'response' non è una lista")
            return []
        return [self._normalize(item) for item in response]

    @staticmethod
    def _normalize(item: Dict[str, Any]) -> Dict[str, Any]:
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})

        return {
            "fixture_id": fixture.get("id"),
            "league_id": league.get("id"),
            "season": league.get("season"),
            "date_utc": fixture.get("date"),
            "home_team": teams.get("home", {}).get("name"),
            "away_team": teams.get("away", {}).get("name"),
            "status": (fixture.get("status") or {}).get("short"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "provider": "api_football",
        }
