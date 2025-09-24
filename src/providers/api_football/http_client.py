import random
import time
from typing import Any, Dict, Optional

import requests

from core.config import get_settings
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
        start_time = time.time()
        attempts_done = 0

        for attempt in range(1, self._max_attempts + 1):
            attempts_done = attempt
            if attempt == 1:
                log.info(f"api_football GET {path} params={params}")
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_reason = f"network:{e.__class__.__name__}"
                if attempt == self._max_attempts:
                    duration = time.time() - start_time
                    log.error(
                        f"api_football GET fail path={path} attempts={attempt}/{self._max_attempts} "
                        f"reason={last_reason} duration={duration:.2f}s"
                    )
                    raise TransientAPIError(
                        f"Errore di rete persistente dopo {attempt} tentativi: {e}"
                    ) from e
                wait = self._compute_delay(attempt)
                log.warning(
                    f"retry attempt={attempt}/{self._max_attempts} wait={wait:.2f}s reason={last_reason}"
                )
                time.sleep(wait)
                continue

            last_status = resp.status_code

            if 200 <= resp.status_code < 300:
                try:
                    data = resp.json()
                except ValueError as e:
                    duration = time.time() - start_time
                    log.error(
                        f"api_football GET invalid_json path={path} attempts={attempt}/{self._max_attempts} "
                        f"status={resp.status_code} duration={duration:.2f}s"
                    )
                    raise RuntimeError(
                        f"Risposta non valida (non JSON) status={resp.status_code}"
                    ) from e
                duration = time.time() - start_time
                if attempt == 1:
                    log.info(
                        f"api_football GET success path={path} attempts=1 duration={duration:.2f}s"
                    )
                else:
                    log.warning(
                        f"api_football GET success_after_retry path={path} attempts={attempt} "
                        f"retries={attempt-1} duration={duration:.2f}s last_status={resp.status_code}"
                    )
                return data

            # HTTP 429 rate limit
            if resp.status_code == 429:
                last_reason = "rate_limit"
                if attempt == self._max_attempts:
                    duration = time.time() - start_time
                    log.error(
                        f"api_football GET rate_limit_exhausted path={path} attempts={attempt}/{self._max_attempts} "
                        f"duration={duration:.2f}s"
                    )
                    raise RateLimitError(f"Rate limit dopo {attempt} tentativi (429).")
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
                log.warning(
                    f"retry attempt={attempt}/{self._max_attempts} wait={wait:.2f}s reason=rate_limit"
                )
                time.sleep(wait)
                continue

            # HTTP 5xx transitori
            if resp.status_code in (500, 502, 503, 504):
                last_reason = f"http_{resp.status_code}"
                if attempt == self._max_attempts:
                    duration = time.time() - start_time
                    log.error(
                        f"api_football GET transient_exhausted path={path} status={resp.status_code} "
                        f"attempts={attempt}/{self._max_attempts} duration={duration:.2f}s"
                    )
                    raise TransientAPIError(
                        f"Status {resp.status_code} persistente dopo {attempt} tentativi."
                    )
                wait = self._compute_delay(attempt)
                log.warning(
                    f"retry attempt={attempt}/{self._max_attempts} wait={wait:.2f}s reason=http_{resp.status_code}"
                )
                time.sleep(wait)
                continue

            # Altri 4xx -> fail fast
            if 400 <= resp.status_code < 500:
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"raw": resp.text}
                duration = time.time() - start_time
                log.error(
                    f"api_football GET client_error path={path} status={resp.status_code} "
                    f"attempts={attempt}/{self._max_attempts} duration={duration:.2f}s"
                )
                raise ValueError(
                    f"Richiesta API fallita (status={resp.status_code}) non retriable: {payload}"
                )

            # Altri codici non retriable
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}
            duration = time.time() - start_time
            log.error(
                f"api_football GET unexpected_status path={path} status={resp.status_code} "
                f"attempts={attempt}/{self._max_attempts} duration={duration:.2f}s"
            )
            raise RuntimeError(
                f"Risposta inattesa (status={resp.status_code}) non retriable: {payload}"
            )

        # Non dovrebbe arrivare qui
        duration = time.time() - start_time
        raise RuntimeError(
            f"Fallimento imprevisto path={path} attempts={attempts_done}/{self._max_attempts} "
            f"last_status={last_status} reason={last_reason} duration={duration:.2f}s"
        )


_client_singleton: Optional[APIFootballHttpClient] = None


def get_http_client() -> APIFootballHttpClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = APIFootballHttpClient()
    return _client_singleton
