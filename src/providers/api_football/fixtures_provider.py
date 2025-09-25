from typing import Any, Dict, Optional, List

from core.config import get_settings
from core.persistence import save_latest_fixtures, clear_latest_fixtures_file
from core.logging import get_logger
# Re-export di _client_singleton per compatibilità con i test di integrazione
from .http_client import get_http_client, _client_singleton  # noqa: F401
from .client import ApiFootballClient

log = get_logger(__name__)


class APIFootballFixturesProvider:
    """
    Provider che usa il client basato su requests (mockato nei test di retry/persistenza).
    Mantiene la compatibilità con i test che importano APIFootballFixturesProvider e _client_singleton.
    """
    def __init__(self):
        self._settings = get_settings()
        self._client = get_http_client()

    def fetch_fixtures(
        self,
        date: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        if league_id or self._settings.default_league_id:
            params["league"] = league_id or self._settings.default_league_id
        if season or self._settings.default_season:
            params["season"] = season or self._settings.default_season

        data = self._client.api_get("/fixtures", params=params or None)
        response = data.get("response", [])

        if not isinstance(response, list):
            log.warning("Formato inatteso: 'response' non è una lista")
            # Se la persistenza è disabilitata, assicuriamoci di non lasciare file sporchi
            if not self._settings.persist_fixtures:
                clear_latest_fixtures_file()
            return []

        if self._settings.persist_fixtures and response:
            try:
                save_latest_fixtures(response)
            except Exception as e:  # best effort, non bloccare il flusso
                log.error(f"persist fixtures raised unexpected error={e}")
        else:
            # Persistenza disabilitata o risposta vuota -> pulisci l’eventuale file canonico
            clear_latest_fixtures_file()

        return response


class ApiFootballFixturesProvider:
    """
    Provider che usa il client basato su httpx (mockato nel test di normalizzazione)
    e normalizza l'output nelle chiavi attese dal test.
    """
    def __init__(self, client: Optional[ApiFootballClient] = None):
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
            log.warning("Formato inatteso: 'response' non è una lista")
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


# Alias per compatibilità con i test che importano ApiFootballFixturesProvider
ApiFootballFixturesProvider = ApiFootballFixturesProvider
