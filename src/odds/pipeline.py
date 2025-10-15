from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Protocol

from core.config import get_settings
from core.logging import get_logger
from providers.odds.odds_provider_stub import StubOddsProvider
from providers.odds.odds_provider_model import ModelOddsProvider  # nuovo provider

logger = get_logger("odds.pipeline")


class OddsProviderProtocol(Protocol):
    def fetch_odds(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...


def run_odds_pipeline(fixtures: List[Dict[str, Any]], provider_name: Optional[str] = None) -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_odds_ingestion:
        logger.info("Odds ingestion disabilitata (ENABLE_ODDS_INGESTION=0).")
        return None

    base = Path(settings.bet_data_dir or "data")
    o_dir = base / settings.odds_dir
    o_dir.mkdir(parents=True, exist_ok=True)
    target = o_dir / "odds_latest.json"

    # Selezione provider: param > settings > env > default "model"
    p_name = (
        provider_name
        or getattr(settings, "odds_provider", None)
        or os.getenv("ODDS_PROVIDER")
        or "model"
    )

    provider: OddsProviderProtocol
    if p_name == "stub":
        provider = StubOddsProvider()
    elif p_name == "model":
        provider = ModelOddsProvider()
    else:
        logger.warning("Provider odds '%s' non supportato, fallback 'model'.", p_name)
        provider = ModelOddsProvider()

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
