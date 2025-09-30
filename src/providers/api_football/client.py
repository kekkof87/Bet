import time
from typing import Any, Dict, Optional

import httpx

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class ApiFootballClient:
    """
    Client HTTP minimale per l'API Football (api-sports).
    Gestisce header API key e logging basilare (debug/errore).
    """

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.api_football_key
        self._headers = {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        }

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Esegue una GET sincrona e ritorna il JSON decodificato.
        Lancia eccezioni httpx in caso di problemi di rete o status != 200.
        """
        params = params or {}
        url = f"{self.BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        logger.debug("GET %s params=%s", url, params)
        start = time.perf_counter()
        try:
            resp = httpx.get(url, params=params, headers=self._headers, timeout=30)
        except httpx.RequestError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Errore rete %s dopo %.1fms: %s", url, elapsed, exc)
            raise
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            logger.error(
                "Status %s %s (%.1fms) body=%s",
                resp.status_code,
                url,
                elapsed,
                resp.text[:300],
            )
            resp.raise_for_status()
        logger.debug("OK %s %s %.1fms", url, resp.status_code, elapsed)
        return resp.json()
