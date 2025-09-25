import random
import time
from typing import Any, Dict, Optional

import requests
from urllib.parse import urlencode

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
        # attempt parte da 1
        delay = self._base * (self._factor ** (attempt - 1))
        if self._jitter > 0:
            delta = self._jitter
            mult = random.uniform(1 - delta, 1 + delta)
            delay *= mult
        return delay

    def api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Log sempre i parametri per i test
        log.info(f"api_football GET {path} params={params}")
        url = _BASE_URL + path
        if params:
            # Evita di passare 'params=' alla sessione (compatibilità con mock dei test)
            query = urlencode(params, doseq=True)
            url = f"{url}?{query}"

        last_status = None
        last_reason = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                # Non passiamo 'params=' per evitare TypeError con il mock
                resp = self._session.get(url, timeout=self._timeout)
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

            # Altri codici -> non retriable
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


# Manteniamo il simbolo per compatibilità con eventuali import nei test
_client_singleton: Optional[APIFootballHttpClient] = None


def get_http_client() -> APIFootballHttpClient:
    """
    Restituisce sempre una nuova istanza per far sì che i test
    che cambiano le variabili d'ambiente (es. API_FOOTBALL_MAX_ATTEMPTS)
    abbiano effetto immediato.
    """
    return APIFootballHttpClient()
