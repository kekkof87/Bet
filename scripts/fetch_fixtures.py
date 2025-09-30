from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider

# Placeholder per future stats unificate (quando il provider userà il client con retry)
try:
    from providers.api_football.http_client import get_http_client  # type: ignore
except Exception:  # pragma: no cover
    get_http_client = None  # type: ignore


def main() -> None:
    """
    Fetch fixtures + diff dettagliato (classification) + history opzionale + structured logging.

    Funzionalità:
      - Abort su fetch vuoto se FETCH_ABORT_ON_EMPTY=1
      - Compare keys (DELTA_COMPARE_KEYS)
      - Classification (score_change / status_change / both / other)
      - History snapshots se ENABLE_HISTORY=1 (rotazione HISTORY_MAX)
      - Structured logging: delta_summary, change_breakdown, fetch_stats (placeholder)
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
    new: List[Dict[str, Any]] = provider.fetch_fixtures(
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

    # Diff dettagliato con classification
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

    # Salva previous solo se esisteva un old
    if old:
        try:
            save_previous_fixtures(old)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore salvataggio previous: %s", exc)

    # Salva latest (anche vuoto se non abortito)
    try:
        save_latest_fixtures(new)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore salvataggio latest: %s", exc)

    # History opzionale
    if settings.enable_history:
        try:
            save_history_snapshot(new)
            rotate_history(settings.history_max)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore history: %s", exc)

    # Riepilogo delta
    summary = summarize_delta(added, removed, modified, len(new))
    if compare_keys:
        summary["compare_keys"] = ",".join(compare_keys)

    # Telemetria fetch (placeholder finché non si unifica il client)
    fetch_stats: Dict[str, Any] = {}
    if get_http_client:
        # get_http_client() qui creerebbe una nuova istanza senza stats utili
        # Verrà sostituito quando il provider userà il client con retry condiviso
        pass

    logger.info(
        "fixtures_delta",
        extra={
            "delta_summary": summary,
            "change_breakdown": change_breakdown,
            "fetch_stats": fetch_stats,
        },
    )

    if new:
        logger.info("Esempio prima fixture", extra={"first_fixture": new[0]})
    else:
        logger.info("Nessuna fixture ottenuta.")


if __name__ == "__main__":
    main()