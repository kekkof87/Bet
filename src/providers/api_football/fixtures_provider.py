from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger
from core.normalization import normalize_api_football_fixture
from core.persistence import (
    clear_latest_fixtures_file,
    save_latest_fixtures,
)
from .http_client import get_http_client, APIFootballHttpClient

log = get_logger(__name__)


class APIFootballFixturesProvider:
    """
    LEGACY Provider (compat per test esistenti).
    - Usa APIFootballHttpClient (requests + retry)
    - NON normalizza (restituisce 'response' grezza)
    - Gestisce persistenza diretta (se API_FOOTBALL_PERSIST_FIXTURES=true)
    """

    def __init__(self, client: Optional[APIFootballHttpClient] = None) -> None:
        self._settings = get_settings()
        self._client = client or get_http_client()

    def fetch_fixtures(
        self,
        *,
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
            if not self._settings.persist_fixtures:
                clear_latest_fixtures_file()
            return []

        if self._settings.persist_fixtures and response:
            try:
                save_latest_fixtures(response)
            except Exception as e:  # pragma: no cover
                log.error("Persist fixtures raised unexpected error=%s", e)
        else:
            clear_latest_fixtures_file()

        return response

    def get_last_stats(self) -> Dict[str, Any]:
        return self._client.get_stats()


class ApiFootballFixturesProvider:
    """
    Provider UNIFICATO normalizzato.
    - Usa APIFootballHttpClient
    - Normalizza i record
    - Nessuna persistenza automatica
    """

    def __init__(self, client: Optional[APIFootballHttpClient] = None) -> None:
        self._client = client or get_http_client()
        self._last_raw: Dict[str, Any] | None = None

    def fetch_fixtures(
        self,
        *,
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

        raw = self._client.api_get("/fixtures", params=params or None)
        self._last_raw = raw
        response = raw.get("response", [])
        if not isinstance(response, list):
            log.warning("Formato inatteso: 'response' non è una lista")
            return []
        return [normalize_api_football_fixture(item) for item in response]

    def get_last_stats(self) -> Dict[str, Any]:
        return self._client.get_stats()


__all__ = [
    "APIFootballFixturesProvider",  # legacy (tests persistence)
    "ApiFootballFixturesProvider",  # normalizzato
]
