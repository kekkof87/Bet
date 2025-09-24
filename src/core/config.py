import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    api_football_key: str
    default_league_id: Optional[int]
    default_season: Optional[int]
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("API_FOOTBALL_KEY")
        if not key:
            raise ValueError(
                "API_FOOTBALL_KEY non impostata. Aggiungi a .env: API_FOOTBALL_KEY=LA_TUA_CHIAVE"
            )

        def _opt_int(name: str) -> Optional[int]:
            raw = os.getenv(name)
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                raise ValueError(f"Variabile {name} deve essere un intero (valore: {raw!r})")

        league_id = _opt_int("API_FOOTBALL_DEFAULT_LEAGUE_ID")
        season = _opt_int("API_FOOTBALL_DEFAULT_SEASON")
        log_level = os.getenv("BET_LOG_LEVEL", "INFO").upper()

        return cls(
            api_football_key=key,
            default_league_id=league_id,
            default_season=season,
            log_level=log_level,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def _reset_settings_cache_for_tests():
    get_settings.cache_clear()  # type: ignore