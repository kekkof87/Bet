import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

from core.config import _reset_settings_cache_for_tests, get_settings
from core.logging import get_logger
from providers.api_football.fixtures_provider import ApiFootballFixturesProvider
from predictions.pipeline import run_baseline_predictions
from analytics.roi import build_or_update_roi

log = get_logger("cycle")

def _iso_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _load_latest_fixtures_file(base: Path) -> List[Dict[str, Any]]:
    # In questa implementazione puntiamo al provider normalizzato (che non persiste)
    # Se si volesse usare la persistenza legacy, si potrebbe leggere da data/fixtures_latest.json
    return []

def main() -> int:
    # Forziamo rilettura settings ad ogni run (evita cache se workflow modifica variabili)
    _reset_settings_cache_for_tests()
    settings = get_settings()

    base = Path(settings.bet_data_dir or "data")
    base.mkdir(parents=True, exist_ok=True)

    log.info("cycle_start", extra={
        "regime_enabled": settings.enable_roi_regime,
        "regime_version": getattr(settings, "roi_regime_version", "n/a"),
        "kelly": settings.enable_kelly_staking,
    })

    # 1. Fetch fixtures (normalizzato)
    provider = ApiFootballFixturesProvider()
    try:
        fixtures = provider.fetch_fixtures(date=_iso_today())
    except Exception as e:
        log.error("fixtures_fetch_error %s", e)
        fixtures = []

    if not fixtures:
        log.warning("no_fixtures_fetched")

    # 2. Predictions (se abilitate)
    try:
        run_baseline_predictions(fixtures)
    except Exception as e:
        log.error("predictions_failed %s", e)

    # 3. ROI update
    try:
        build_or_update_roi(fixtures)
    except Exception as e:
        log.error("roi_update_failed %s", e)

    log.info("cycle_complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
