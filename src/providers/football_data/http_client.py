import os
from typing import Any, Dict, Optional
import requests


class FootballDataClient:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 20) -> None:
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise ValueError("FOOTBALL_DATA_API_KEY non impostata.")
        self.timeout = timeout
        self._last_status: Optional[int] = None

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        headers = {"X-Auth-Token": self.api_key}
        resp = requests.get(url, headers=headers, params=params or {}, timeout=self.timeout)
        self._last_status = resp.status_code
        resp.raise_for_status()
        return resp.json()

    def last_status(self) -> Optional[int]:
        return self._last_status
