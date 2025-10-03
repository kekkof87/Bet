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

    enable_merged_value_alerts: bool
    merged_value_edge_policy: str
    roi_include_merged: bool

    enable_roi_csv_export: bool
    roi_csv_file: str
    roi_csv_include_open: bool
    roi_csv_sort: str
    roi_csv_limit: int

    roi_max_new_picks_per_day: int
    roi_rate_limit_strict: bool

    value_alert_dynamic_enable: bool
    value_alert_dynamic_target_count: int
    value_alert_dynamic_min_factor: float
    value_alert_dynamic_max_factor: float
    value_alert_dynamic_adjust_step: float

    enable_clv_capture: bool
    clv_odds_source: str

    merged_dedup_enable: bool

    roi_rolling_window: int
    enable_roi_edge_deciles: bool
    enable_roi_clv_aggregate: bool

    roi_rolling_windows: List[int]
    enable_roi_source_breakdown: bool
    enable_roi_risk_metrics: bool
    enable_roi_stake_breakdown: bool
    roi_ledger_max_picks: int
    roi_ledger_max_age_days: int
    enable_roi_ledger_archive: bool
    enable_roi_latency_metrics: bool
    enable_roi_league_breakdown: bool
    roi_league_max: int
    enable_roi_time_buckets: bool
    roi_edge_buckets_raw: Optional[str]
    roi_edge_buckets: List[str]

    # Batch 37 CORE NEW
    enable_roi_equity_vol: bool
    roi_equity_vol_windows: List[int]

    enable_roi_anomaly_flags: bool
    roi_anomaly_dd_threshold: float
    roi_anomaly_yield_drop: float
    roi_anomaly_vol_mult: float

    enable_roi_schema_export: bool
    enable_roi_profit_distribution: bool
    enable_roi_ror: bool
    enable_roi_source_efficiency: bool

    # Batch 37 PLUS NEW
    enable_roi_edge_clv_corr: bool
    enable_roi_stake_advisory: bool
    roi_stake_advisory_dd_pct: float
    enable_roi_aging_buckets: bool
    roi_aging_buckets: List[int]
    enable_roi_side_breakdown: bool
    enable_roi_clv_buckets: bool
    roi_clv_buckets_raw: Optional[str]
    roi_clv_buckets: List[str]

    # Batch 38 Advanced
    enable_roi_kelly_effect: bool
    enable_roi_payout_moments: bool
    enable_roi_market_placeholder: bool
    enable_roi_compact_export: bool
    enable_roi_archive_stats: bool
    enable_roi_montecarlo: bool
    roi_mc_runs: int
    roi_mc_window: int
    enable_roi_profit_buckets: bool
    roi_profit_buckets_raw: Optional[str]
    roi_profit_buckets: List[str]

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
        consensus_baseline_weight = max(0.0, min(consensus_baseline_weight, 1.0))

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
        model_adjust_weight = max(0.0, min(model_adjust_weight, 1.0))

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
        kelly_edge_cap = max(0.0, min(kelly_edge_cap, 1.0))

        enable_roi_odds_snapshot = _parse_bool(os.getenv("ENABLE_ROI_ODDS_SNAPSHOT"), True)

        enable_merged_value_alerts = _parse_bool(os.getenv("ENABLE_MERGED_VALUE_ALERTS"), False)
        merged_value_edge_policy = os.getenv("MERGED_VALUE_EDGE_POLICY", "max").lower()
        if merged_value_edge_policy not in {"max", "min", "avg"}:
            merged_value_edge_policy = "max"
        roi_include_merged = _parse_bool(os.getenv("ROI_INCLUDE_MERGED"), True)

        enable_roi_csv_export = _parse_bool(os.getenv("ENABLE_ROI_CSV_EXPORT"), True)
        roi_csv_file = os.getenv("ROI_CSV_FILE", "roi_export.csv")
        roi_csv_include_open = _parse_bool(os.getenv("ROI_CSV_INCLUDE_OPEN"), True)
        roi_csv_sort = os.getenv("ROI_CSV_SORT", "created_at")
        if roi_csv_sort not in {"created_at", "settled_at"}:
            roi_csv_sort = "created_at"
        roi_csv_limit = _int("ROI_CSV_LIMIT", 0)

        roi_max_new_picks_per_day = _int("ROI_MAX_NEW_PICKS_PER_DAY", 0)
        roi_rate_limit_strict = _parse_bool(os.getenv("ROI_RATE_LIMIT_STRICT"), True)

        value_alert_dynamic_enable = _parse_bool(os.getenv("VALUE_ALERT_DYNAMIC_ENABLE"), False)
        value_alert_dynamic_target_count = _int("VALUE_ALERT_DYNAMIC_TARGET_COUNT", 50)
        value_alert_dynamic_min_factor = _float("VALUE_ALERT_DYNAMIC_MIN_FACTOR", 1.0)
        value_alert_dynamic_max_factor = _float("VALUE_ALERT_DYNAMIC_MAX_FACTOR", 2.0)
        value_alert_dynamic_adjust_step = _float("VALUE_ALERT_DYNAMIC_ADJUST_STEP", 0.05)

        enable_clv_capture = _parse_bool(os.getenv("ENABLE_CLV_CAPTURE"), True)
        clv_odds_source = os.getenv("CLV_ODDS_SOURCE", "odds_latest").lower()

        merged_dedup_enable = _parse_bool(os.getenv("MERGED_DEDUP_ENABLE"), False)

        roi_rolling_window = _int("ROI_ROLLING_WINDOW", 30)
        if roi_rolling_window < 1:
            roi_rolling_window = 30

        enable_roi_edge_deciles = _parse_bool(os.getenv("ENABLE_ROI_EDGE_DECILES"), True)
        enable_roi_clv_aggregate = _parse_bool(os.getenv("ENABLE_ROI_CLV_AGGREGATE"), True)

        rolling_windows_raw = os.getenv("ROI_ROLLING_WINDOWS", "7,30,90")
        rw_list: List[int] = []
        for token in rolling_windows_raw.split(","):
            t = token.strip()
            if not t:
                continue
            try:
                val = int(t)
                if val > 0:
                    rw_list.append(val)
            except ValueError:
                continue
        if not rw_list:
            rw_list = [7, 30, 90]

        enable_roi_source_breakdown = _parse_bool(os.getenv("ENABLE_ROI_SOURCE_BREAKDOWN"), True)
        enable_roi_risk_metrics = _parse_bool(os.getenv("ENABLE_ROI_RISK_METRICS"), True)
        enable_roi_stake_breakdown = _parse_bool(os.getenv("ENABLE_ROI_STAKE_BREAKDOWN"), True)
        roi_ledger_max_picks = _int("ROI_LEDGER_MAX_PICKS", 0)
        roi_ledger_max_age_days = _int("ROI_LEDGER_MAX_AGE_DAYS", 0)
        enable_roi_ledger_archive = _parse_bool(os.getenv("ENABLE_ROI_LEDGER_ARCHIVE"), True)
        enable_roi_latency_metrics = _parse_bool(os.getenv("ENABLE_ROI_LATENCY_METRICS"), True)
        enable_roi_league_breakdown = _parse_bool(os.getenv("ENABLE_ROI_LEAGUE_BREAKDOWN"), False)
        roi_league_max = _int("ROI_LEAGUE_MAX", 10)
        enable_roi_time_buckets = _parse_bool(os.getenv("ENABLE_ROI_TIME_BUCKETS"), False)
        roi_edge_buckets_raw = os.getenv("ROI_EDGE_BUCKETS", "0.05-0.07,0.07-0.09,0.09-0.12,0.12-")
        roi_edge_buckets = [r.strip() for r in roi_edge_buckets_raw.split(",") if r.strip()]

        # Batch 37 core
        enable_roi_equity_vol = _parse_bool(os.getenv("ENABLE_ROI_EQUITY_VOL"), True)
        eq_vol_raw = os.getenv("ROI_EQUITY_VOL_WINDOWS", "30,100")
        roi_equity_vol_windows: List[int] = []
        for t in eq_vol_raw.split(","):
            t = t.strip()
            if not t:
                continue
            try:
                iv = int(t)
                if iv > 1:
                    roi_equity_vol_windows.append(iv)
            except ValueError:
                continue
        if not roi_equity_vol_windows:
            roi_equity_vol_windows = [30, 100]

        enable_roi_anomaly_flags = _parse_bool(os.getenv("ENABLE_ROI_ANOMALY_FLAGS"), True)
        roi_anomaly_dd_threshold = _float("ROI_ANOMALY_DD_THRESHOLD", 0.30)
        roi_anomaly_yield_drop = _float("ROI_ANOMALY_YIELD_DROP", 0.50)
        roi_anomaly_vol_mult = _float("ROI_ANOMALY_VOL_MULT", 2.0)

        enable_roi_schema_export = _parse_bool(os.getenv("ENABLE_ROI_SCHEMA_EXPORT"), False)
        enable_roi_profit_distribution = _parse_bool(os.getenv("ENABLE_ROI_PROFIT_DISTRIBUTION"), True)
        enable_roi_ror = _parse_bool(os.getenv("ENABLE_ROI_ROR"), False)
        enable_roi_source_efficiency = _parse_bool(os.getenv("ENABLE_ROI_SOURCE_EFFICIENCY"), True)

        # Batch 37 plus
        enable_roi_edge_clv_corr = _parse_bool(os.getenv("ENABLE_ROI_EDGE_CLV_CORR"), False)
        enable_roi_stake_advisory = _parse_bool(os.getenv("ENABLE_ROI_STAKE_ADVISORY"), False)
        roi_stake_advisory_dd_pct = _float("ROI_STAKE_ADVISORY_DD_PCT", 0.25)

        enable_roi_aging_buckets = _parse_bool(os.getenv("ENABLE_ROI_AGING_BUCKETS"), False)
        aging_raw = os.getenv("ROI_AGING_BUCKETS", "1,2,3,5,7")
        roi_aging_buckets: List[int] = []
        for t in aging_raw.split(","):
            t = t.strip()
            if not t:
                continue
            try:
                iv = int(t)
                if iv > 0:
                    roi_aging_buckets.append(iv)
            except ValueError:
                continue
        roi_aging_buckets = sorted(set(roi_aging_buckets))

        enable_roi_side_breakdown = _parse_bool(os.getenv("ENABLE_ROI_SIDE_BREAKDOWN"), True)
        enable_roi_clv_buckets = _parse_bool(os.getenv("ENABLE_ROI_CLV_BUCKETS"), False)
        roi_clv_buckets_raw = os.getenv("ROI_CLV_BUCKETS", "-0.1--0.05,-0.05-0,0-0.05,0-0.05,0.05-0.1,0.1-")
        roi_clv_buckets = [r.strip() for r in roi_clv_buckets_raw.split(",") if r.strip()]

        # Batch 38 advanced
        enable_roi_kelly_effect = _parse_bool(os.getenv("ENABLE_ROI_KELLY_EFFECT"), False)
        enable_roi_payout_moments = _parse_bool(os.getenv("ENABLE_ROI_PAYOUT_MOMENTS"), False)
        enable_roi_market_placeholder = _parse_bool(os.getenv("ENABLE_ROI_MARKET_PLACEHOLDER"), False)
        enable_roi_compact_export = _parse_bool(os.getenv("ENABLE_ROI_COMPACT_EXPORT"), False)
        enable_roi_archive_stats = _parse_bool(os.getenv("ENABLE_ROI_ARCHIVE_STATS"), False)
        enable_roi_montecarlo = _parse_bool(os.getenv("ENABLE_ROI_MONTECARLO"), False)
        roi_mc_runs = _int("ROI_MC_RUNS", 500)
        roi_mc_window = _int("ROI_MC_WINDOW", 200)
        enable_roi_profit_buckets = _parse_bool(os.getenv("ENABLE_ROI_PROFIT_BUCKETS"), False)
        roi_profit_buckets_raw = os.getenv("ROI_PROFIT_BUCKETS", "-2--1,-1--0.5,-0.5-0,0-0.5,0.5-1,1-")
        roi_profit_buckets = [r.strip() for r in roi_profit_buckets_raw.split(",") if r.strip()]

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
            enable_roi_csv_export=enable_roi_csv_export,
            roi_csv_file=roi_csv_file,
            roi_csv_include_open=roi_csv_include_open,
            roi_csv_sort=roi_csv_sort,
            roi_csv_limit=roi_csv_limit,
            roi_max_new_picks_per_day=roi_max_new_picks_per_day,
            roi_rate_limit_strict=roi_rate_limit_strict,
            value_alert_dynamic_enable=value_alert_dynamic_enable,
            value_alert_dynamic_target_count=value_alert_dynamic_target_count,
            value_alert_dynamic_min_factor=value_alert_dynamic_min_factor,
            value_alert_dynamic_max_factor=value_alert_dynamic_max_factor,
            value_alert_dynamic_adjust_step=value_alert_dynamic_adjust_step,
            enable_clv_capture=enable_clv_capture,
            clv_odds_source=clv_odds_source,
            merged_dedup_enable=merged_dedup_enable,
            roi_rolling_window=roi_rolling_window,
            enable_roi_edge_deciles=enable_roi_edge_deciles,
            enable_roi_clv_aggregate=enable_roi_clv_aggregate,
            roi_rolling_windows=rw_list,
            enable_roi_source_breakdown=enable_roi_source_breakdown,
            enable_roi_risk_metrics=enable_roi_risk_metrics,
            enable_roi_stake_breakdown=enable_roi_stake_breakdown,
            roi_ledger_max_picks=roi_ledger_max_picks,
            roi_ledger_max_age_days=roi_ledger_max_age_days,
            enable_roi_ledger_archive=enable_roi_ledger_archive,
            enable_roi_latency_metrics=enable_roi_latency_metrics,
            enable_roi_league_breakdown=enable_roi_league_breakdown,
            roi_league_max=roi_league_max,
            enable_roi_time_buckets=enable_roi_time_buckets,
            roi_edge_buckets_raw=roi_edge_buckets_raw,
            roi_edge_buckets=roi_edge_buckets,
            enable_roi_equity_vol=enable_roi_equity_vol,
            roi_equity_vol_windows=roi_equity_vol_windows,
            enable_roi_anomaly_flags=enable_roi_anomaly_flags,
            roi_anomaly_dd_threshold=roi_anomaly_dd_threshold,
            roi_anomaly_yield_drop=roi_anomaly_yield_drop,
            roi_anomaly_vol_mult=roi_anomaly_vol_mult,
            enable_roi_schema_export=enable_roi_schema_export,
            enable_roi_profit_distribution=enable_roi_profit_distribution,
            enable_roi_ror=enable_roi_ror,
            enable_roi_source_efficiency=enable_roi_source_efficiency,
            enable_roi_edge_clv_corr=enable_roi_edge_clv_corr,
            enable_roi_stake_advisory=enable_roi_stake_advisory,
            roi_stake_advisory_dd_pct=roi_stake_advisory_dd_pct,
            enable_roi_aging_buckets=enable_roi_aging_buckets,
            roi_aging_buckets=roi_aging_buckets,
            enable_roi_side_breakdown=enable_roi_side_breakdown,
            enable_roi_clv_buckets=enable_roi_clv_buckets,
            roi_clv_buckets_raw=roi_clv_buckets_raw,
            roi_clv_buckets=roi_clv_buckets,
            enable_roi_kelly_effect=enable_roi_kelly_effect,
            enable_roi_payout_moments=enable_roi_payout_moments,
            enable_roi_market_placeholder=enable_roi_market_placeholder,
            enable_roi_compact_export=enable_roi_compact_export,
            enable_roi_archive_stats=enable_roi_archive_stats,
            enable_roi_montecarlo=enable_roi_montecarlo,
            roi_mc_runs=roi_mc_runs,
            roi_mc_window=roi_mc_window,
            enable_roi_profit_buckets=enable_roi_profit_buckets,
            roi_profit_buckets_raw=roi_profit_buckets_raw,
            roi_profit_buckets=roi_profit_buckets,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def _reset_settings_cache_for_tests() -> None:
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "_reset_settings_cache_for_tests"]
