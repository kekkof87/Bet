"""
DEPRECATED: questo client httpx semplice è mantenuto solo per riferimento transitorio.
Usare ApiFootballFixturesProvider (fixtures_provider.py) che ora si basa su APIFootballHttpClient
(con retry/backoff + telemetria) e normalizzazione centralizzata.

In una futura iterazione questo file potrà essere rimosso del tutto.
"""
import time
from typing import Any, Dict, Optional

import httpx

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class ApiFootballClient:
    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.api_football_key
        self._headers = {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        url = f"{self.BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        logger.debug("DEPRECATED httpx GET %s params=%s", url, params)
        start = time.perf_counter()
        resp = httpx.get(url, params=params, headers=self._headers, timeout=30)
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            logger.error("DEPRECATED client status %s url=%s body=%s", resp.status_code, url, resp.text[:250])
            resp.raise_for_status()
        logger.debug("DEPRECATED client OK %s %.1fms", url, elapsed)
        return resp.json()
