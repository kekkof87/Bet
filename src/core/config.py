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
    enable_predictions_use_odds: bool

    enable_consensus: bool
    consensus_dir: str
    consensus_baseline_weight: float

    enable_telegram_parser: bool
    telegram_raw_dir: str
    telegram_parsed_dir: str

    enable_prometheus_exporter: bool
    prometheus_port: int

    enable_odds_ingestion: bool
    odds_dir: str
    odds_provider: str
    odds_default_source: str

    enable_alert_dispatch: bool
    alert_dispatch_mode: str
    alert_webhook_url: Optional[str]
    alert_telegram_bot_token: Optional[str]
    alert_telegram_chat_id: Optional[str]

    enable_value_detection: bool
    value_min_edge: float
    value_include_adjusted: bool

    value_alert_min_edge: float
    enable_value_alerts: bool
    value_alerts_dir: str

    enable_value_history: bool
    value_history_dir: str
    value_history_max_files: int
    value_history_mode: str

    enable_model_adjust: bool
    model_adjust_weight: float

    enable_roi_tracking: bool
    roi_dir: str
    roi_min_edge: float
    roi_include_consensus: bool
    roi_stake_units: float

    enable_roi_timeline: bool
    roi_timeline_file: str
    roi_daily_file: str

    enable_kelly_staking: bool
    kelly_base_units: float
    kelly_max_units: float
    kelly_edge_cap: float

    enable_roi_odds_snapshot: bool

    # Merged value alerts
    enable_merged_value_alerts: bool
    merged_value_edge_policy: str  # max|min|avg
    roi_include_merged: bool

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("API_FOOTBALL_KEY")
        if not key:
            raise ValueError("API_FOOTBALL_KEY non impostata. Aggiungi a .env: API_FOOTBALL_KEY=LA_TUA_CHIAVE")

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
        enable_predictions_use_odds = _parse_bool(os.getenv("ENABLE_PREDICTIONS_USE_ODDS"), False)

        enable_consensus = _parse_bool(os.getenv("ENABLE_CONSENSUS"), False)
        consensus_dir = os.getenv("CONSENSUS_DIR", "consensus")
        consensus_baseline_weight = _float("CONSENSUS_BASELINE_WEIGHT", 0.6)
        if consensus_baseline_weight < 0:
            consensus_baseline_weight = 0.0
        if consensus_baseline_weight > 1:
            consensus_baseline_weight = 1.0

        enable_telegram_parser = _parse_bool(os.getenv("ENABLE_TELEGRAM_PARSER"), False)
        telegram_raw_dir = os.getenv("TELEGRAM_RAW_DIR", "telegram/raw")
        telegram_parsed_dir = os.getenv("TELEGRAM_PARSED_DIR", "telegram/parsed")

        enable_prometheus_exporter = _parse_bool(os.getenv("ENABLE_PROMETHEUS_EXPORTER"), False)
        prometheus_port = _int("PROMETHEUS_PORT", 9100)

        enable_odds_ingestion = _parse_bool(os.getenv("ENABLE_ODDS_INGESTION"), False)
        odds_dir = os.getenv("ODDS_DIR", "odds")
        odds_provider = os.getenv("ODDS_PROVIDER", "stub")
        odds_default_source = os.getenv("ODDS_DEFAULT_SOURCE", "stub-book")

        enable_alert_dispatch = _parse_bool(os.getenv("ENABLE_ALERT_DISPATCH"), False)
        alert_dispatch_mode = os.getenv("ALERT_DISPATCH_MODE", "stdout").lower()
        alert_webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        alert_telegram_bot_token = os.getenv("ALERT_TELEGRAM_BOT_TOKEN")
        alert_telegram_chat_id = os.getenv("ALERT_TELEGRAM_CHAT_ID")

        enable_value_detection = _parse_bool(os.getenv("ENABLE_VALUE_DETECTION"), False)
        value_min_edge = _float("VALUE_MIN_EDGE", 0.05)
        value_include_adjusted = _parse_bool(os.getenv("VALUE_INCLUDE_ADJUSTED"), True)

        value_alert_min_edge = _float("VALUE_ALERT_MIN_EDGE", value_min_edge)
        enable_value_alerts = _parse_bool(os.getenv("ENABLE_VALUE_ALERTS"), False)
        value_alerts_dir = os.getenv("VALUE_ALERTS_DIR", "value_alerts")

        enable_value_history = _parse_bool(os.getenv("ENABLE_VALUE_HISTORY"), False)
        value_history_dir = os.getenv("VALUE_HISTORY_DIR", "value_history")
        value_history_max_files = _int("VALUE_HISTORY_MAX_FILES", 30)
        value_history_mode = os.getenv("VALUE_HISTORY_MODE", "daily").lower()
        if value_history_mode not in {"daily", "rolling"}:
            value_history_mode = "daily"

        enable_model_adjust = _parse_bool(os.getenv("ENABLE_MODEL_ADJUST"), False)
        model_adjust_weight = _float("MODEL_ADJUST_WEIGHT", 0.7)
        if model_adjust_weight < 0:
            model_adjust_weight = 0.0
        if model_adjust_weight > 1:
            model_adjust_weight = 1.0

        enable_roi_tracking = _parse_bool(os.getenv("ENABLE_ROI_TRACKING"), False)
        roi_dir = os.getenv("ROI_DIR", "roi")
        roi_min_edge = _float("ROI_MIN_EDGE", 0.05)
        roi_include_consensus = _parse_bool(os.getenv("ROI_INCLUDE_CONSENSUS"), True)
        roi_stake_units = _float("ROI_STAKE_UNITS", 1.0)

        enable_roi_timeline = _parse_bool(os.getenv("ENABLE_ROI_TIMELINE"), True)
        roi_timeline_file = os.getenv("ROI_TIMELINE_FILE", "roi_history.jsonl")
        roi_daily_file = os.getenv("ROI_DAILY_FILE", "roi_daily.json")

        enable_kelly_staking = _parse_bool(os.getenv("ENABLE_KELLY_STAKING"), False)
        kelly_base_units = _float("KELLY_BASE_UNITS", 1.0)
        kelly_max_units = _float("KELLY_MAX_UNITS", 3.0)
        kelly_edge_cap = _float("KELLY_EDGE_CAP", 0.5)
        if kelly_edge_cap < 0:
            kelly_edge_cap = 0.0
        if kelly_edge_cap > 1:
            kelly_edge_cap = 1.0

        enable_roi_odds_snapshot = _parse_bool(os.getenv("ENABLE_ROI_ODDS_SNAPSHOT"), True)

        enable_merged_value_alerts = _parse_bool(os.getenv("ENABLE_MERGED_VALUE_ALERTS"), False)
        merged_value_edge_policy = os.getenv("MERGED_VALUE_EDGE_POLICY", "max").lower()
        if merged_value_edge_policy not in {"max", "min", "avg"}:
            merged_value_edge_policy = "max"
        roi_include_merged = _parse_bool(os.getenv("ROI_INCLUDE_MERGED"), True)

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
            enable_predictions_use_odds=enable_predictions_use_odds,
            enable_consensus=enable_consensus,
            consensus_dir=consensus_dir,
            consensus_baseline_weight=consensus_baseline_weight,
            enable_telegram_parser=enable_telegram_parser,
            telegram_raw_dir=telegram_raw_dir,
            telegram_parsed_dir=telegram_parsed_dir,
            enable_prometheus_exporter=enable_prometheus_exporter,
            prometheus_port=prometheus_port,
            enable_odds_ingestion=enable_odds_ingestion,
            odds_dir=odds_dir,
            odds_provider=odds_provider,
            odds_default_source=odds_default_source,
            enable_alert_dispatch=enable_alert_dispatch,
            alert_dispatch_mode=alert_dispatch_mode,
            alert_webhook_url=alert_webhook_url,
            alert_telegram_bot_token=alert_telegram_bot_token,
            alert_telegram_chat_id=alert_telegram_chat_id,
            enable_value_detection=enable_value_detection,
            value_min_edge=value_min_edge,
            value_include_adjusted=value_include_adjusted,
            value_alert_min_edge=value_alert_min_edge,
            enable_value_alerts=enable_value_alerts,
            value_alerts_dir=value_alerts_dir,
            enable_value_history=enable_value_history,
            value_history_dir=value_history_dir,
            value_history_max_files=value_history_max_files,
            value_history_mode=value_history_mode,
            enable_model_adjust=enable_model_adjust,
            model_adjust_weight=model_adjust_weight,
            enable_roi_tracking=enable_roi_tracking,
            roi_dir=roi_dir,
            roi_min_edge=roi_min_edge,
            roi_include_consensus=roi_include_consensus,
            roi_stake_units=roi_stake_units,
            enable_roi_timeline=enable_roi_timeline,
            roi_timeline_file=roi_timeline_file,
            roi_daily_file=roi_daily_file,
            enable_kelly_staking=enable_kelly_staking,
            kelly_base_units=kelly_base_units,
            kelly_max_units=kelly_max_units,
            kelly_edge_cap=kelly_edge_cap,
            enable_roi_odds_snapshot=enable_roi_odds_snapshot,
            enable_merged_value_alerts=enable_merged_value_alerts,
            merged_value_edge_policy=merged_value_edge_policy,
            roi_include_merged=roi_include_merged,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def _reset_settings_cache_for_tests() -> None:
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "_reset_settings_cache_for_tests"]
