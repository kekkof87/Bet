from __future__ import annotations

from typing import Any, Dict, List, cast, TYPE_CHECKING

from core.config import get_settings
from core.logging import get_logger
from core.persistence import load_latest_fixtures
from odds.pipeline import run_odds_pipeline

if TYPE_CHECKING:
    from core.models import FixtureRecord  # noqa: F401

logger = get_logger("scripts.fetch_odds")


def main() -> None:
    # Verifica configurazione (API_FOOTBALL_KEY comunque richiesta dal sistema)
    try:
        get_settings()
    except ValueError as e:
        logger.error("Config non valida: %s", e)
        return

    loaded = load_latest_fixtures()
    if not isinstance(loaded, list):
        logger.error("fixtures_latest non disponibile o formattata male.")
        return

    # Non tipizziamo rigidamente: ci basta trattarli come dict serializzati
    fixtures = loaded  # type: ignore[assignment]
    logger.info("Caricate %d fixtures per odds.", len(fixtures))

    try:
        run_odds_pipeline(cast(List[Dict[str, Any]], fixtures))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore esecuzione odds pipeline: %s", exc)


if __name__ == "__main__":
    main()
