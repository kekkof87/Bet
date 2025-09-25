import random
import time
from typing import Any, Dict, Optional, List

import requests

from core.config import get_settings
from core.persistence import save_latest_fixtures
from core.logging import get_logger
from .exceptions import RateLimitError, TransientAPIError

log = get_logger(__name__)

_BASE_URL = "https://v3.football.api-sports.io"


class APIFootballHttpClient:
    def __init__(self):
        self._settings = get_settings()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "x-apisports-key": self._settings.api_football_key,
                "Accept": "application/json",
            }
        )
        self._max_attempts = self._settings.api_football_max_attempts
        self._base = self._settings.api_football_backoff_base
        self._factor = self._settings.api_football_backoff_factor
        self._jitter = self._settings.api_football_backoff_jitter
        self._timeout = self._settings.api_football_timeout

    def _compute_delay(self, attempt: int) -> float:
        # attempt parte da 1
        delay = self._base * (self._factor ** (attempt - 1))
        if self._jitter > 0:
            delta = self._jitter
            mult = random.uniform(1 - delta, 1 + delta)
            delay *= mult
        return delay

    def api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = _BASE_URL + path
        last_status = None
        last_reason = None

        for attempt in range(1, self._max_attempts + 1):
            if attempt == 1:
                log.info(f"api_football GET {path} params={params}")
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_reason = f"network:{e.__class__.__name__}"
                if attempt == self._max_attempts:
                    raise TransientAPIError(
                        f"Errore di rete persistente dopo {attempt} tentativi: {e}"
                    ) from e
                wait = self._compute_delay(attempt)
                log.warning(f"retry attempt={attempt} wait={wait:.2f}s reason={last_reason}")
                time.sleep(wait)
                continue

            last_status = resp.status_code

            if 200 <= resp.status_code < 300:
                try:
                    return resp.json()
                except ValueError as e:
                    # Risposta non JSON -> consideriamo non transitorio
                    raise RuntimeError(f"Risposta non valida (non JSON) status={resp.status_code}") from e

            # Gestione 429 (rate limit)
            if resp.status_code == 429:
                last_reason = "rate_limit"
                if attempt == self._max_attempts:
                    raise RateLimitError(f"Rate limit dopo {attempt} tentativi (429).")
                # calcolo delay
                retry_after_header = resp.headers.get("Retry-After")
                computed = self._compute_delay(attempt)
                if retry_after_header:
                    try:
                        ra = float(retry_after_header)
                        wait = max(computed, ra)
                    except ValueError:
                        wait = computed
                else:
                    wait = computed
                log.warning(f"retry attempt={attempt} wait={wait:.2f}s reason=rate_limit")
                time.sleep(wait)
                continue

            # Retry su 5xx transitori
            if resp.status_code in (500, 502, 503, 504):
                last_reason = f"http_{resp.status_code}"
                if attempt == self._max_attempts:
                    raise TransientAPIError(
                        f"Status {resp.status_code} persistente dopo {attempt} tentativi."
                    )
                wait = self._compute_delay(attempt)
                log.warning(f"retry attempt={attempt} wait={wait:.2f}s reason=http_{resp.status_code}")
                time.sleep(wait)
                continue

            # Altri 4xx -> fail fast
            if 400 <= resp.status_code < 500:
                # Proviamo a estrarre messaggio server
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"raw": resp.text}
                raise ValueError(
                    f"Richiesta API fallita (status={resp.status_code}) non retriable: {payload}"
                )

            # Altri codici (es. 3xx / 418 / ecc.) li trattiamo come non retriable
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}
            raise RuntimeError(
                f"Risposta inattesa (status={resp.status_code}) non retriable: {payload}"
            )

        # In teoria non si arriva qui
        raise RuntimeError(
            f"Fallimento imprevisto path={path} last_status={last_status} reason={last_reason}"
        )


_client_singleton: Optional[APIFootballHttpClient] = None


def get_http_client() -> APIFootballHttpClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = APIFootballHttpClient()
    return _client_singleton


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
            return []

        if self._settings.persist_fixtures and response:
            try:
                save_latest_fixtures(response)
            except Exception as e:  # best effort, non bloccare il flusso
                log.error(f"persist fixtures raised unexpected error={e}")

        return response


# Alias per compatibilità con i test che importano ApiFootballFixturesProvider
ApiFootballFixturesProvider = APIFootballFixturesProvider
