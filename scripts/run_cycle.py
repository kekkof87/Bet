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


def main() -> int:
    """
    Esegue un ciclo completo:
      1. Reload settings (per applicare variabili aggiornate nei workflow)
      2. Fetch fixtures del giorno (normalizzate)
      3. Predictions (se abilitate)
      4. ROI build/update (ledger + metrics + regime + export)
    """
    _reset_settings_cache_for_tests()
    settings = get_settings()

    base = Path(settings.bet_data_dir or "data")
    base.mkdir(parents=True, exist_ok=True)

    log.info(
        "cycle_start",
        extra={
            "regime_enabled": settings.enable_roi_regime,
            "regime_version": getattr(settings, "roi_regime_version", "n/a"),
            "kelly": settings.enable_kelly_staking,
        },
    )

    provider = ApiFootballFixturesProvider()

    # Primo tentativo: solo data odierna (lega/stagione dalle env)
    try:
        fixtures: List[Dict[str, Any]] = provider.fetch_fixtures(
            date=_iso_today(),
            league_id=settings.default_league_id,
            season=settings.default_season,
        )
    except Exception as e:  # pragma: no cover (difensivo)
        log.error("fixtures_fetch_error %s", e)
        fixtures = []

    # Fallback: se vuoto, allarga a tutte le leghe (stessa data)
    if not fixtures:
        log.warning(
            "no_fixtures_fetched for league=%s season=%s on %s. Fallback to ALL leagues for today.",
            settings.default_league_id,
            settings.default_season,
            _iso_today(),
        )
        try:
            fixtures = provider.fetch_fixtures(date=_iso_today(), league_id=None, season=None)
        except Exception as e:  # pragma: no cover
            log.error("fixtures_fallback_error %s", e)
            fixtures = []

    if not fixtures:
        log.warning("still_no_fixtures_after_fallback")

    # 2. Predictions
    try:
        run_baseline_predictions(fixtures)
    except Exception as e:  # pragma: no cover
        log.error("predictions_failed %s", e)

    # 3. ROI update
    try:
        build_or_update_roi(fixtures)
    except Exception as e:  # pragma: no cover
        log.error("roi_update_failed %s", e)

    log.info("cycle_complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
