from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
from pathlib import Path

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
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider


def _load_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> None:
    """
    Fetch fixtures + diff dettagliato + history opzionale + metrics/events + scoreboard.
    """
    logger = get_logger("scripts.fetch_fixtures")

    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("%s", e)
        logger.error("Aggiungi API_FOOTBALL_KEY nel file .env oppure come variabile ambiente.")
        return

    old: List[Dict[str, Any]] = load_latest_fixtures()
    if not isinstance(old, list):
        logger.warning("Snapshot precedente non valido, uso old=[]")
        old = []

    logger.info("Avvio fetch fixtures (API-Football)...")
    provider = ApiFootballFixturesProvider()
    new = provider.fetch_fixtures(
        league_id=settings.default_league_id,
        season=settings.default_season,
        date=None,
    )
    if not isinstance(new, list):
        logger.error("Provider ha restituito tipo inatteso %s, forzo lista vuota", type(new))
        new = []

    if settings.fetch_abort_on_empty and not new:
        logger.warning("Fetch vuoto e FETCH_ABORT_ON_EMPTY=1: abort senza aggiornare stato.")
        return

    compare_keys: Optional[List[str]] = settings.delta_compare_keys

    try:
        detailed = diff_fixtures_detailed(
            old,
            new,
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

    summary = summarize_delta(added, removed, modified, len(new))
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

    # Costruzione scoreboard (usa i dati appena generati)
    try:
        scoreboard = build_scoreboard(
            fixtures=new,
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

    if new:
        logger.info("Esempio prima fixture", extra={"first_fixture": new[0]})
    else:
        logger.info("Nessuna fixture ottenuta.")


if __name__ == "__main__":
    main()