import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, List


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    v = value.strip().lower()
    if v in {"0", "false", "no"}:
        return False
    return True


def _parse_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    clean = [p for p in parts if p]
    return clean or None


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
    bet_data_dir: str

    delta_compare_keys: Optional[List[str]]
    fetch_abort_on_empty: bool

    enable_history: bool
    history_max: int

    enable_metrics_file: bool
    enable_events_file: bool
    metrics_dir: str
    events_dir: str

    enable_alerts_file: bool
    alerts_dir: str
    alert_status_sequence: Optional[List[str]]
    alert_include_final: bool

    enable_predictions: bool
    predictions_dir: str
    model_baseline_version: str

    # NEW (consensus)
    enable_consensus: bool
    consensus_dir: str

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
            except ValueError as e:
                raise ValueError(f"Variabile {name} deve essere un intero (valore: {raw!r})") from e

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError as e:
                raise ValueError(f"Variabile {name} deve essere un intero (valore: {raw!r})") from e

        def _float(name: str, default: float) -> float:
            raw = os.getenv(name)
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError as e:
                raise ValueError(f"Variabile {name} deve essere un numero (valore: {raw!r})") from e

        league_id = _opt_int("API_FOOTBALL_DEFAULT_LEAGUE_ID")
        season = _opt_int("API_FOOTBALL_DEFAULT_SEASON")
        log_level = os.getenv("BET_LOG_LEVEL", "INFO").upper()

        max_attempts = _int("API_FOOTBALL_MAX_ATTEMPTS", 5)
        backoff_base = _float("API_FOOTBALL_BACKOFF_BASE", 0.5)
        backoff_factor = _float("API_FOOTBALL_BACKOFF_FACTOR", 2.0)
        backoff_jitter = _float("API_FOOTBALL_BACKOFF_JITTER", 0.2)
        timeout = _float("API_FOOTBALL_TIMEOUT", 10.0)

        persist_fixtures = _parse_bool(os.getenv("API_FOOTBALL_PERSIST_FIXTURES"), True)
        bet_data_dir = os.getenv("BET_DATA_DIR", "data")

        delta_compare_keys = _parse_list(os.getenv("DELTA_COMPARE_KEYS"))
        fetch_abort_on_empty = _parse_bool(os.getenv("FETCH_ABORT_ON_EMPTY"), False)

        enable_history = _parse_bool(os.getenv("ENABLE_HISTORY"), False)
        history_max = _int("HISTORY_MAX", 30)

        enable_metrics_file = _parse_bool(os.getenv("ENABLE_METRICS_FILE"), True)
        enable_events_file = _parse_bool(os.getenv("ENABLE_EVENTS_FILE"), True)
        metrics_dir = os.getenv("METRICS_DIR", "metrics")
        events_dir = os.getenv("EVENTS_DIR", "events")

        enable_alerts_file = _parse_bool(os.getenv("ENABLE_ALERTS_FILE"), True)
        alerts_dir = os.getenv("ALERTS_DIR", "alerts")
        alert_status_sequence = _parse_list(os.getenv("ALERT_STATUS_SEQUENCE"))
        alert_include_final = _parse_bool(os.getenv("ALERT_INCLUDE_FINAL"), True)

        enable_predictions = _parse_bool(os.getenv("ENABLE_PREDICTIONS"), False)
        predictions_dir = os.getenv("PREDICTIONS_DIR", "predictions")
        model_baseline_version = os.getenv("MODEL_BASELINE_VERSION", "baseline-v1")

        enable_consensus = _parse_bool(os.getenv("ENABLE_CONSENSUS"), False)
        consensus_dir = os.getenv("CONSENSUS_DIR", "consensus")

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
            delta_compare_keys=delta_compare_keys,
            fetch_abort_on_empty=fetch_abort_on_empty,
            enable_history=enable_history,
            history_max=history_max,
            enable_metrics_file=enable_metrics_file,
            enable_events_file=enable_events_file,
            metrics_dir=metrics_dir,
            events_dir=events_dir,
            enable_alerts_file=enable_alerts_file,
            alerts_dir=alerts_dir,
            alert_status_sequence=alert_status_sequence,
            alert_include_final=alert_include_final,
            enable_predictions=enable_predictions,
            predictions_dir=predictions_dir,
            model_baseline_version=model_baseline_version,
            enable_consensus=enable_consensus,
            consensus_dir=consensus_dir,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def _reset_settings_cache_for_tests() -> None:
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "_reset_settings_cache_for_tests"]
