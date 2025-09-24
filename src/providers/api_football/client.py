import time
from typing import Any, Dict, Optional

import httpx

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class ApiFootballClient:
    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.api_football_key
        self._headers = {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        url = f"{self.BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        logger.debug(f"GET {url} params={params}")
        start = time.perf_counter()
        try:
            resp = httpx.get(url, params=params, headers=self._headers, timeout=30)
        except httpx.RequestError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(f"Errore rete {url} dopo {elapsed:.1f}ms: {exc}")
            raise
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            logger.error(f"Status {resp.status_code} {url} ({elapsed:.1f}ms) body={resp.text[:300]}")
            resp.raise_for_status()
        logger.debug(f"OK {url} {resp.status_code} {elapsed:.1f}ms")
        return resp.json()