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
        # Legacy mantiene i default sempre (comportamento test vecchi)
        if league_id or self._settings.default_league_id:
            params["league"] = league_id or self._settings.default_league_id
        if season or self._settings.default_season:
            params["season"] = season or self._settings.default_season

        # NUOVO: con data ma senza lega, evita ALL-LEAGUES (coerente con i test)
        if date and "league" not in params:
            log.info("Data specificata ma nessuna lega; skip ALL-LEAGUES (legacy). date=%s", date)
            if not self._settings.persist_fixtures:
                clear_latest_fixtures_file()
            return []

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

        # Applica SEMPRE i default se presenti
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date

        if league_id is not None:
            params["league"] = league_id
        elif settings.default_league_id is not None:
            params["league"] = settings.default_league_id

        if season is not None:
            params["season"] = season
        elif settings.default_season is not None:
            params["season"] = settings.default_season

        # Regola deterministica per i test: se c'è la data ma nessuna lega, NON fare ALL-LEAGUES → ritorna [].
        if date and "league" not in params:
            log.info("Data specificata ma nessuna lega; skip ALL-LEAGUES (normalized). date=%s", date)
            self._last_raw = {"response": []}
            return []

        raw = self._client.api_get("/fixtures", params=params or None)
        self._last_raw = raw
        response = raw.get("response", [])
        if not isinstance(response, list):
            log.warning("Formato inatteso: 'response' non è una lista")
            return []
        return [normalize_api_football_fixture(item) for item in response]

    def get_last_stats(self) -> Dict[str, Any]:
        return self._client.get_stats()

    def get_last_raw(self) -> Dict[str, Any]:
        return self._last_raw or {}


__all__ = [
    "APIFootballFixturesProvider",
    "ApiFootballFixturesProvider",
]
