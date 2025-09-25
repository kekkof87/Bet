from typing import Any, Dict, Optional, List

from core.config import get_settings
from core.persistence import save_latest_fixtures, clear_latest_fixtures_file
from core.logging import get_logger
# Re-export di _client_singleton per compatibilità con i test
from .http_client import get_http_client, _client_singleton  # noqa: F401

log = get_logger(__name__)


class APIFootballFixturesProvider:
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
            # Se la persistenza è disabilitata, assicurati che il file canonico non resti sporco
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


# Alias per compatibilità con i test che importano ApiFootballFixturesProvider
ApiFootballFixturesProvider = APIFootballFixturesProvider
