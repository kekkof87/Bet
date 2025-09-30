from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.diff import diff_fixtures_detailed, summarize_delta
from core.logging import get_logger
from core.persistence import (
    load_latest_fixtures,
    save_latest_fixtures,
    save_previous_fixtures,
)
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider


def main() -> None:
    """
    Fetch + delta classification (score/status) + structured logging.
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
        logger.warning("Fetch vuoto e FETCH_ABORT_ON_EMPTY=1: non salvo stato, non aggiorno previous.")
        return

    compare_keys: Optional[List[str]] = settings.delta_compare_keys

    # Diff dettagliato
    try:
        detailed = diff_fixtures_detailed(
            old,
            new,
            compare_keys=compare_keys if compare_keys else None,
            classify=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Errore diff dettagliato: %s", exc)
        detailed = {"added": [], "removed": [], "modified": [], "change_breakdown": {"score_change": 0, "status_change": 0, "both": 0, "other": 0}}

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

    summary = summarize_delta(added, removed, modified, len(new))
    if compare_keys:
        summary = {**summary, "compare_keys": ",".join(compare_keys)}

    logger.info("fixtures_delta", extra={"delta_summary": summary, "change_breakdown": change_breakdown})

    if new:
        logger.info("Esempio prima fixture", extra={"first_fixture": new[0]})
    else:
        logger.info("Nessuna fixture ottenuta.")


if __name__ == "__main__":
    main()
