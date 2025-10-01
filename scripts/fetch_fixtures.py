from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, cast, TYPE_CHECKING

from core.config import get_settings
from core.diff import diff_fixtures_detailed, summarize_delta
from core.logging import get_logger
from core.persistence import (
    load_latest_fixtures,
    save_latest_fixtures,
    save_previous_fixtures,
    save_history_snapshot,
    rotate_history,
)
from core.metrics import write_metrics_snapshot, write_last_delta_event
from core.scoreboard import build_scoreboard, write_scoreboard
from core.alerts import build_alerts, write_alerts
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider
from odds.pipeline import run_odds_pipeline
from predictions.pipeline import run_baseline_predictions
from consensus.pipeline import run_consensus_pipeline
from monitoring.prometheus_exporter import update_prom_metrics

if TYPE_CHECKING:
    from core.models import FixtureRecord  # noqa: F401


def _load_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> None:
    logger = get_logger("scripts.fetch_fixtures")

    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("%s", e)
        logger.error("Aggiungi API_FOOTBALL_KEY nel file .env oppure come variabile ambiente.")
        return

    loaded_old = load_latest_fixtures()
    if not isinstance(loaded_old, list):
        logger.warning("Snapshot precedente non valido, uso old=[]")
        loaded_old = []
    old = cast(List["FixtureRecord"], loaded_old)

    logger.info("Avvio fetch fixtures (API-Football)...")
    provider = ApiFootballFixturesProvider()
    loaded_new = provider.fetch_fixtures(
        league_id=settings.default_league_id,
        season=settings.default_season,
        date=None,
    )
    if not isinstance(loaded_new, list):
        logger.error("Provider ha restituito tipo inatteso %s, forzo lista vuota", type(loaded_new))
        loaded_new = []
    new = cast(List["FixtureRecord"], loaded_new)

    if settings.fetch_abort_on_empty and not new:
        logger.warning("Fetch vuoto e FETCH_ABORT_ON_EMPTY=1: abort senza aggiornare stato.")
        return

    compare_keys: Optional[List[str]] = settings.delta_compare_keys
    try:
        detailed = diff_fixtures_detailed(
            cast(List[Dict[str, Any]], old),
            cast(List[Dict[str, Any]], new),
            compare_keys=compare_keys if compare_keys else None,
            classify=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Errore diff dettagliato: %s", exc)
        detailed = {
            "added": [],
            "removed": [],
            "modified": [],
            "change_breakdown": {
                "score_change": 0,
                "status_change": 0,
                "both": 0,
                "other": 0,
            },
        }

    added = detailed["added"]
    removed = detailed["removed"]
    modified = detailed["modified"]
    change_breakdown = detailed["change_breakdown"]

    if old:
        try:
            save_previous_fixtures(old)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore salvataggio previous: %s", exc)

    try:
        save_latest_fixtures(new)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore salvataggio latest: %s", exc)

    if settings.enable_history:
        try:
            save_history_snapshot(new)
            rotate_history(settings.history_max)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore history: %s", exc)

    base_summary = summarize_delta(added, removed, modified, len(new))
    summary: Dict[str, Any] = dict(base_summary)
    if compare_keys:
        summary["compare_keys"] = ",".join(compare_keys)

    fetch_stats = provider.get_last_stats()

    logger.info(
        "fixtures_delta",
        extra={
            "delta_summary": summary,
            "change_breakdown": change_breakdown,
            "fetch_stats": fetch_stats,
        },
    )

    metrics_payload = {
        "summary": summary,
        "change_breakdown": change_breakdown,
        "fetch_stats": fetch_stats,
        "total_fixtures": len(new),
    }
    try:
        write_metrics_snapshot(metrics_payload)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore scrittura metrics snapshot: %s", exc)

    delta_event = {
        "added": added,
        "removed": removed,
        "modified": modified,
        "change_breakdown": change_breakdown,
    }
    try:
        if added or removed or modified:
            write_last_delta_event(delta_event)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore scrittura delta event: %s", exc)

    # Alerts (score / status)
    try:
        alerts = build_alerts(modified)
        if alerts:
            write_alerts(alerts)
        logger.info("fixtures_alerts", extra={"alerts_count": len(alerts)})
    except Exception as exc:  # pragma: no cover
        logger.error("Errore generazione alerts: %s", exc)

    # Scoreboard
    try:
        scoreboard = build_scoreboard(
            fixtures=cast(List[Dict[str, Any]], new),
            metrics=metrics_payload,
            delta=delta_event if (added or removed or modified) else None,
        )
        write_scoreboard(scoreboard)
        logger.info(
            "scoreboard_generated",
            extra={
                "live": scoreboard["live_count"],
                "upcoming": scoreboard["upcoming_count_next_24h"],
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Errore generazione scoreboard: %s", exc)

    # Odds ingestion (prima delle predictions)
    try:
        run_odds_pipeline(cast(List[Dict[str, Any]], new))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore odds pipeline: %s", exc)

    # Predictions
    try:
        run_baseline_predictions(cast(List[Dict[str, Any]], new))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore predictions baseline: %s", exc)

    # Consensus
    try:
        run_consensus_pipeline()
    except Exception as exc:  # pragma: no cover
        logger.error("Errore consensus pipeline: %s", exc)

    # Value alerts + history + dispatch
    value_alerts_list: List[Dict[str, Any]] = []
    try:
        if settings.enable_value_alerts:
            from predictions.value_alerts import build_value_alerts, write_value_alerts
            value_alerts_list = build_value_alerts()
            if value_alerts_list:
                write_value_alerts(value_alerts_list)
                if settings.enable_value_history:
                    try:
                        from predictions.value_history import append_value_history
                        append_value_history(value_alerts_list)
                    except Exception as exc2:  # pragma: no cover
                        logger.error("Errore append value history: %s", exc2)
                if settings.enable_alert_dispatch:
                    try:
                        from notifications.dispatcher import dispatch_alerts
                        dispatch_payload = [
                            {
                                "type": "value_alert",
                                "fixture_id": a.get("fixture_id"),
                                "value_side": a.get("value_side"),
                                "value_edge": a.get("value_edge"),
                                "source": a.get("source"),
                            }
                            for a in value_alerts_list
                        ]
                        dispatch_alerts(dispatch_payload)
                    except Exception as exc2:  # pragma: no cover
                        logger.error("Errore dispatch value alerts: %s", exc2)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore value alerts pipeline: %s", exc)

    # ROI tracking (post value alerts e dopo eventuali fixture FT)
    try:
        if settings.enable_roi_tracking:
            from analytics.roi import build_or_update_roi
            build_or_update_roi(cast(List[Dict[str, Any]], new))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore ROI tracking: %s", exc)

    # Prometheus exporter one-shot
    try:
        update_prom_metrics()
    except Exception as exc:  # pragma: no cover
        logger.error("Errore aggiornamento metriche Prometheus: %s", exc)

    if new:
        logger.info("Esempio prima fixture", extra={"first_fixture": cast(List[Dict[str, Any]], new)[0]})
    else:
        logger.info("Nessuna fixture ottenuta.")


if __name__ == "__main__":
    main()
