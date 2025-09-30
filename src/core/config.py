import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    v = value.strip().lower()
    if v in {"0", "false", "no"}:
        return False
    return True


@dataclass
class Settings:
    api_football_key: str
    default_league_id: Optional[int]
    default_season: Optional[int]
    log_level: str

    api_football_max_attempts: int
    api_football_backoff_base: float
    api_football_backoff_factor: float
    api_football_backoff_jitter: float
    api_football_timeout: float

    persist_fixtures: bool
    bet_data_dir: str  # directory base dati

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("API_FOOTBALL_KEY")
        if not key:
            raise ValueError(
                "API_FOOTBALL_KEY non impostata. Aggiungi a .env: "
                "API_FOOTBALL_KEY=LA_TUA_CHIAVE"
            )

        def _opt_int(name: str) -> Optional[int]:
            raw = os.getenv(name)
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError as e:
                raise ValueError(
                    f"Variabile {name} deve essere un intero (valore: {raw!r})"
                ) from e

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError as e:
                raise ValueError(
                    f"Variabile {name} deve essere un intero (valore: {raw!r})"
                ) from e

        def _float(name: str, default: float) -> float:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError as e:
                raise ValueError(
                    f"Variabile {name} deve essere un numero (valore: {raw!r})"
                ) from e

        league_id = _opt_int("API_FOOTBALL_DEFAULT_LEAGUE_ID")
        season = _opt_int("API_FOOTBALL_DEFAULT_SEASON")
        log_level = os.getenv("BET_LOG_LEVEL", "INFO").upper()

        max_attempts = _int("API_FOOTBALL_MAX_ATTEMPTS", 5)
        backoff_base = _float("API_FOOTBALL_BACKOFF_BASE", 0.5)
        backoff_factor = _float("API_FOOTBALL_BACKOFF_FACTOR", 2.0)
        backoff_jitter = _float("API_FOOTBALL_BACKOFF_JITTER", 0.2)
        timeout = _float("API_FOOTBALL_TIMEOUT", 10.0)

        persist_fixtures = _parse_bool(
            os.getenv("API_FOOTBALL_PERSIST_FIXTURES"),
            True,
        )
        bet_data_dir = os.getenv("BET_DATA_DIR", "data")

        return cls(
            api_football_key=key,
            default_league_id=league_id,
            default_season=season,
            log_level=log_level,
            api_football_max_attempts=max_attempts,
            api_football_backoff_base=backoff_base,
            api_football_backoff_factor=backoff_factor,
            api_football_backoff_jitter=backoff_jitter,
            api_football_timeout=timeout,
            persist_fixtures=persist_fixtures,
            bet_data_dir=bet_data_dir,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def _reset_settings_cache_for_tests() -> None:
    """Supporto ai test: svuota la cache di get_settings()."""
    get_settings.cache_clear()


__all__ = [
    "Settings",
    "get_settings",
    "_reset_settings_cache_for_tests",
]
