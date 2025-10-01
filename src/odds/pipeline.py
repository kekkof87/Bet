from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_settings
from core.logging import get_logger
from providers.odds.odds_provider_stub import StubOddsProvider

logger = get_logger("odds.pipeline")


def run_odds_pipeline(fixtures: List[Dict[str, Any]], provider_name: Optional[str] = None) -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_odds_ingestion:
        logger.info("Odds ingestion disabilitata (ENABLE_ODDS_INGESTION=0).")
        return None

    base = Path(settings.bet_data_dir or "data")
    o_dir = base / settings.odds_dir
    o_dir.mkdir(parents=True, exist_ok=True)
    target = o_dir / "odds_latest.json"

    p_name = provider_name or settings.odds_provider
    if p_name == "stub":
        provider = StubOddsProvider()
    else:
        logger.warning("Provider odds '%s' non supportato, fallback stub.", p_name)
        provider = StubOddsProvider()

    odds_entries = provider.fetch_odds(fixtures)
    payload = {
        "provider": p_name,
        "count": len(odds_entries),
        "entries": odds_entries,
    }
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    logger.info("odds_pipeline_written", extra={"count": len(odds_entries), "provider": p_name})
    return target


__all__ = ["run_odds_pipeline"]
