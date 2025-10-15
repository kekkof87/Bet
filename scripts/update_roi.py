from __future__ import annotations

from typing import Any, Dict, List, cast, TYPE_CHECKING

from core.config import get_settings
from core.logging import get_logger
from core.persistence import load_latest_fixtures
from analytics.roi import build_or_update_roi

if TYPE_CHECKING:
    from core.models import FixtureRecord  # noqa: F401

logger = get_logger("scripts.update_roi")


def main() -> None:
    try:
        s = get_settings()
    except ValueError as e:
        logger.error("Configurazione non valida: %s", e)
        return

    if not s.enable_roi_tracking:
        logger.info("ROI tracking disabilitato (ENABLE_ROI_TRACKING=0).")
        return

    loaded = load_latest_fixtures()
    if not isinstance(loaded, list):
        logger.error("fixtures_latest non disponibile o formattata male.")
        return

    fixtures = loaded  # type: ignore[assignment]
    logger.info("Caricate %d fixtures per ROI.", len(fixtures))

    try:
        build_or_update_roi(cast(List[Dict[str, Any]], fixtures))
        logger.info("ROI aggiornato con successo.")
    except Exception as exc:  # pragma: no cover
        logger.error("Errore update ROI: %s", exc)


if __name__ == "__main__":
    main()
