from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from core.config import get_settings
from core.logging import get_logger
from .exceptions import RateLimitError, TransientAPIError

log = get_logger(__name__)

_BASE_URL = "https://v3.football.api-sports.io"


class APIFootballHttpClient:
    """
    Client HTTP con retry e backoff per API Football (versione requests).
    Gestisce rate limit (429), errori transitori (5xx, network) e ritorna JSON.

    Aggiunta telemetria minima:
      - _last_attempts: numero di tentativi effettuati nella ultima chiamata
      - _last_retries: retries (attempts - 1)
      - _last_latency_ms: durata totale in millisecondi (dall'inizio alla conclusione: successo o errore finale)
      - _last_status: ultimo HTTP status code ricevuto (se nessuna risposta -> None)
    """

    def __init__(self) -> None:
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

        # Telemetria (popolata ad ogni api_get)
        self._last_attempts: int = 0
        self._last_retries: int = 0
        self._last_latency_ms: float = 0.0
        self._last_status: Optional[int] = None

    def _compute_delay(self, attempt: int) -> float:
        # attempt parte da 1
        delay = self._base * (self._factor ** (attempt - 1))
        if self._jitter > 0:
            mult = random.uniform(1 - self._jitter, 1 + self._jitter)
            delay *= mult
        return delay

    def api_get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Log sempre i parametri (utile nei test)
        log.info("api_football GET %s params=%s", path, params)
        base_url = _BASE_URL + path

        last_status: Optional[int] = None
        last_reason: Optional[str] = None
        start_overall = time.perf_counter()

        # Reset telemetria (in caso di riuso dello stesso oggetto)
        self._last_attempts = 0
        self._last_retries = 0
        self._last_latency_ms = 0.0
        self._last_status = None

        for attempt in range(1, self._max_attempts + 1):
            url = base_url
            try_with_params = bool(params)

            try:
                if try_with_params:
                    resp = self._session.get(
                        url,
                        params=params,
                        timeout=self._timeout,
                    )
                else:
                    resp = self._session.get(url, timeout=self._timeout)
            except TypeError:
                # Alcuni test monkeypatchano Session.get con firma diversa:
                # fallback: costruiamo l'URL manualmente
                if params:
                    query = urlencode(params, doseq=True)
                    url = f"{url}?{query}"
                resp = self._session.get(url, timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_reason = f"network:{e.__class__.__name__}"
                if attempt == self._max_attempts:
                    # Fallimento finale: aggiorna telemetria e rilancia
                    self._last_attempts = attempt
                    self._last_retries = attempt - 1
                    self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                    self._last_status = None
                    raise TransientAPIError(
                        f"Errore di rete persistente dopo {attempt} tentativi: {e}"
                    ) from e
                wait = self._compute_delay(attempt)
                log.warning(
                    "retry attempt=%s wait=%.2fs reason=%s",
                    attempt,
                    wait,
                    last_reason,
                )
                time.sleep(wait)
                continue

            last_status = resp.status_code
            self._last_status = last_status  # aggiorniamo ogni volta che riceviamo risposta

            # Successo
            if 200 <= resp.status_code < 300:
                try:
                    data = resp.json()
                except ValueError as e:
                    # Telemetria su errore finale
                    self._last_attempts = attempt
                    self._last_retries = attempt - 1
                    self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                    raise RuntimeError(
                        f"Risposta non valida (non JSON) status={resp.status_code}"
                    ) from e
                # Telemetria su successo
                self._last_attempts = attempt
                self._last_retries = attempt - 1
                self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                return data

            # Rate limit 429
            if resp.status_code == 429:
                last_reason = "rate_limit"
                if attempt == self._max_attempts:
                    self._last_attempts = attempt
                    self._last_retries = attempt - 1
                    self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                    raise RateLimitError(
                        f"Rate limit dopo {attempt} tentativi (429)."
                    )
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
                    "retry attempt=%s wait=%.2fs reason=rate_limit",
                    attempt,
                    wait,
                )
                time.sleep(wait)
                continue

            # Errori transitori server
            if resp.status_code in (500, 502, 503, 504):
                last_reason = f"http_{resp.status_code}"
                if attempt == self._max_attempts:
                    self._last_attempts = attempt
                    self._last_retries = attempt - 1
                    self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                    raise TransientAPIError(
                        f"Status {resp.status_code} persistente dopo {attempt} tentativi."
                    )
                wait = self._compute_delay(attempt)
                log.warning(
                    "retry attempt=%s wait=%.2fs reason=http_%s",
                    attempt,
                    wait,
                    resp.status_code,
                )
                time.sleep(wait)
                continue

            # Errori 4xx non recuperabili
            if 400 <= resp.status_code < 500:
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"raw": resp.text}
                self._last_attempts = attempt
                self._last_retries = attempt - 1
                self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
                raise ValueError(
                    f"Richiesta API fallita (status={resp.status_code}) non retriable: {payload}"
                )

            # Altri codici non gestiti
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}
            self._last_attempts = attempt
            self._last_retries = attempt - 1
            self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
            raise RuntimeError(
                f"Risposta inattesa (status={resp.status_code}) non retriable: {payload}"
            )

        # Non dovrebbe mai arrivare qui
        self._last_attempts = self._max_attempts
        self._last_retries = self._max_attempts - 1
        self._last_latency_ms = (time.perf_counter() - start_overall) * 1000
        raise RuntimeError(
            f"Fallimento imprevisto path={path} last_status={last_status} reason={last_reason}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Ritorna telemetria dell'ultima chiamata:
          attempts: tentativi totali
          retries: tentativi falliti (attempts - 1)
          latency_ms: durata complessiva
          last_status: ultimo status code visto (None se mai ricevuta risposta valida)
        """
        return {
            "attempts": self._last_attempts,
            "retries": self._last_retries,
            "latency_ms": round(self._last_latency_ms, 2),
            "last_status": self._last_status,
        }


# Manteniamo il simbolo per compatibilità con eventuali import nei test
_client_singleton: Optional[APIFootballHttpClient] = None


def get_http_client() -> APIFootballHttpClient:
    """
    Restituisce sempre una nuova istanza per far sì che i test che
    modificano le variabili d'ambiente abbiano effetto immediato.
    """
    return APIFootballHttpClient()
