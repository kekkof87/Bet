from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger
from core.persistence import clear_latest_fixtures_file, save_latest_fixtures

# Re-export di _client_singleton per compatibilità con i test di integrazione
from .http_client import _client_singleton, get_http_client  # noqa: F401
from .client import ApiFootballClient

log = get_logger(__name__)


class APIFootballFixturesProvider:
    """
    Provider che usa il client basato su 'requests' (mock nei test di retry/persistenza).
    Mantiene compatibilità con test che importano APIFootballFixturesProvider e _client_singleton.
    """

    def __init__(self) -> None:
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
                log.error("Persist fixtures raised unexpected error=%s", e)
        else:
            # Persistenza disabilitata o risposta vuota -> pulizia file
            clear_latest_fixtures_file()

        return response


class ApiFootballFixturesProvider:
    """
    Provider che usa il client basato su httpx (mock nel test di normalizzazione)
    e normalizza l'output nelle chiavi attese dal test.
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
