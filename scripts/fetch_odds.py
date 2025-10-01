from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.config import get_settings
from core.logging import get_logger
from core.persistence import load_latest_fixtures
from odds.pipeline import run_odds_pipeline

logger = get_logger("scripts.fetch_odds")


def main() -> None:
    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("Config non valida: %s", e)
        return

    latest = load_latest_fixtures()
    if not isinstance(latest, list):
        logger.error("fixtures_latest non disponibile o formattata male.")
        return
    fixtures: List[Dict[str, Any]] = latest
    logger.info("Caricate %d fixtures per odds.", len(fixtures))
    run_odds_pipeline(fixtures)


if __name__ == "__main__":
    main()
