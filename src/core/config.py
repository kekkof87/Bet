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

    # Directory base per dati (fallback se non impostata via env)
    bet_data_dir: str

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
            except ValueError:
                raise
