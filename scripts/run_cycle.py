import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

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
    1) Reload settings
    2) Fetch fixtures (con fallback ai prossimi 7 giorni se 'oggi' è vuoto)
    3) Predictions
    4) ROI update
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

    # 1) Oggi (lega+season se presenti)
    fixtures: List[Dict[str, Any]] = provider.fetch_fixtures(
        date=_iso_today(),
        league_id=settings.default_league_id,
        season=settings.default_season,
    )

    # 2) Fallback: oggi tutte le leghe
    if not fixtures:
        log.warning("no_fixtures_today_for_league_season -> try ALL leagues today")
        fixtures = provider.fetch_fixtures(date=_iso_today(), league_id=None, season=None)

    # 3) Fallback: prossimi 7 giorni tutte le leghe (aggregazione e dedup)
    if not fixtures:
        log.warning("still_no_fixtures_today -> try next 7 days ALL leagues")
        agg: Dict[int, Dict[str, Any]] = {}
        for d in range(1, 8):
            day = (datetime.now(timezone.utc) + timedelta(days=d)).strftime("%Y-%m-%d")
            chunk = provider.fetch_fixtures(date=day, league_id=None, season=None)
            for rec in chunk or []:
                fid = rec.get("fixture_id")
                if fid is not None and fid not in agg:
                    agg[fid] = rec
        fixtures = list(agg.values())

    if not fixtures:
        log.warning("still_no_fixtures_after_7d_fallback")

    # 4) Predictions
    try:
        run_baseline_predictions(fixtures)
    except Exception as e:  # pragma: no cover
        log.error("predictions_failed %s", e)

    # 5) ROI update
    try:
        build_or_update_roi(fixtures)
    except Exception as e:  # pragma: no cover
        log.error("roi_update_failed %s", e)

    log.info("cycle_complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
