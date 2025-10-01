from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)
from core.config import get_settings
from core.logging import get_logger

logger = get_logger("monitoring.prometheus_exporter")

# Registry globale (semplice) – per test usiamo un registry separato.
_REGISTRY = CollectorRegistry()

# Metriche base
FETCH_RUNS_TOTAL = Counter("bet_fetch_runs_total", "Numero esecuzioni fetch", registry=_REGISTRY)
FIXTURES_TOTAL = Gauge("bet_fixtures_total", "Numero totale fixtures dopo ultimo fetch", registry=_REGISTRY)
DELTA_ADDED = Gauge("bet_delta_added", "Delta added ultimo fetch", registry=_REGISTRY)
DELTA_REMOVED = Gauge("bet_delta_removed", "Delta removed ultimo fetch", registry=_REGISTRY)
DELTA_MODIFIED = Gauge("bet_delta_modified", "Delta modified ultimo fetch", registry=_REGISTRY)
CHANGE_SCORE = Gauge("bet_change_score", "Count score_change", registry=_REGISTRY)
CHANGE_STATUS = Gauge("bet_change_status", "Count status_change", registry=_REGISTRY)
CHANGE_BOTH = Gauge("bet_change_both", "Count both", registry=_REGISTRY)
CHANGE_OTHER = Gauge("bet_change_other", "Count other", registry=_REGISTRY)
FETCH_LATENCY_MS = Gauge("bet_fetch_latency_ms", "Ultima latenza fetch in ms", registry=_REGISTRY)
FETCH_RETRIES = Gauge("bet_fetch_retries", "Numero retry ultimo fetch", registry=_REGISTRY)
FETCH_ATTEMPTS = Gauge("bet_fetch_attempts", "Numero tentativi ultimo fetch", registry=_REGISTRY)
SCOREBOARD_LIVE = Gauge("bet_scoreboard_live", "Numero live fixtures scoreboard", registry=_REGISTRY)
SCOREBOARD_UPCOMING_24H = Gauge("bet_scoreboard_upcoming_24h", "Upcoming entro 24h scoreboard", registry=_REGISTRY)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def update_prom_metrics(base_dir: Optional[str] = None) -> None:
    """
    Legge i file prodotti dalla pipeline e aggiorna metriche.
    Non solleva eccezioni (safe best-effort).
    """
    try:
        settings = get_settings()
    except Exception:
        logger.debug("Config non disponibile, skip metrics update")
        return

    if not settings.enable_prometheus_exporter:
        logger.debug("Exporter disabilitato, skip update")
        return

    bdir = Path(base_dir or settings.bet_data_dir or "data")

    # last_run metrics
    metrics_path = bdir / settings.metrics_dir / "last_run.json"
    delta_path = bdir / settings.events_dir / "last_delta.json"
    scoreboard_path = bdir / "scoreboard.json"

    metrics_data = _read_json(metrics_path) or {}
    delta_data = _read_json(delta_path) or {}
    scoreboard_data = _read_json(scoreboard_path) or {}

    # Counters / Gauges
    FETCH_RUNS_TOTAL.inc()

    total_fixtures = metrics_data.get("total_fixtures") or metrics_data.get("summary", {}).get("total_new")
    if isinstance(total_fixtures, int):
        FIXTURES_TOTAL.set(total_fixtures)

    # Delta counts
    d_event = delta_data if delta_data else {}
    added = len(d_event.get("added", []))
    removed = len(d_event.get("removed", []))
    modified = len(d_event.get("modified", []))
    DELTA_ADDED.set(added)
    DELTA_REMOVED.set(removed)
    DELTA_MODIFIED.set(modified)

    # Change breakdown
    cb = d_event.get("change_breakdown") or metrics_data.get("change_breakdown") or {}
    CHANGE_SCORE.set(cb.get("score_change", 0))
    CHANGE_STATUS.set(cb.get("status_change", 0))
    CHANGE_BOTH.set(cb.get("both", 0))
    CHANGE_OTHER.set(cb.get("other", 0))

    # Fetch stats
    fs = metrics_data.get("fetch_stats") or {}
    FETCH_LATENCY_MS.set(fs.get("latency_ms", 0) or 0)
    FETCH_RETRIES.set(fs.get("retries", 0) or 0)
    FETCH_ATTEMPTS.set(fs.get("attempts", 0) or 0)

    # Scoreboard
    SCOREBOARD_LIVE.set(scoreboard_data.get("live_count", 0) or 0)
    SCOREBOARD_UPCOMING_24H.set(scoreboard_data.get("upcoming_count_next_24h", 0) or 0)

    logger.debug("Prometheus metrics updated.")


def generate_prometheus_text() -> bytes:
    return generate_latest(_REGISTRY)


__all__ = ["update_prom_metrics", "generate_prometheus_text", "_REGISTRY"]
