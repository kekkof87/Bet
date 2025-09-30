from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger
from core.normalization import normalize_api_football_fixture
from .http_client import get_http_client, APIFootballHttpClient

log = get_logger(__name__)


class ApiFootballFixturesProvider:
    """
    Provider unificato che:
      - Usa APIFootballHttpClient (requests + retry/backoff)
      - Normalizza i record con funzione centralizzata
      - Espone telemetria dell'ultima chiamata (get_last_stats)
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
        """
        Ritorna le stats (attempts, retries, latency_ms, last_status) dall'HTTP client.
        """
        return self._client.get_stats()


__all__ = ["ApiFootballFixturesProvider"]
