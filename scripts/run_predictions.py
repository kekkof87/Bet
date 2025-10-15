from __future__ import annotations

from typing import Any, Dict, List, cast, TYPE_CHECKING

from core.config import get_settings
from core.logging import get_logger
from core.persistence import load_latest_fixtures
from predictions.pipeline import run_baseline_predictions

if TYPE_CHECKING:
    from core.models import FixtureRecord  # noqa: F401

logger = get_logger("scripts.run_predictions")


def main() -> None:
    try:
        get_settings()
    except ValueError as e:
        logger.error("Configurazione non valida: %s", e)
        return

    loaded = load_latest_fixtures()
    if not isinstance(loaded, list):
        logger.error("fixtures_latest non disponibile o formattata male.")
        return

    fixtures = loaded  # type: ignore[assignment]
    logger.info("Caricate %d fixtures per predictions.", len(fixtures))

    try:
        path = run_baseline_predictions(cast(List[Dict[str, Any]], fixtures))
        logger.info("Predictions completate: %s", path)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore esecuzione predictions: %s", exc)


if __name__ == "__main__":
    main()
