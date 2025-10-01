from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

from core.config import get_settings
from core.logging import get_logger
from predictions.features import build_features
from predictions.model import BaselineModel

logger = get_logger("predictions.pipeline")


def run_baseline_predictions(fixtures: List[Dict[str, Any]]) -> None:
    settings = get_settings()
    if not settings.enable_predictions:
        logger.info("Predictions disabilitate (ENABLE_PREDICTIONS=0)")
        return

    base = Path(settings.bet_data_dir or "data")
    p_dir = base / settings.predictions_dir
    p_dir.mkdir(parents=True, exist_ok=True)
    target = p_dir / "latest_predictions.json"

    features = build_features(fixtures)
    model = BaselineModel(version=settings.model_baseline_version)
    preds = model.predict(features)

    # Se arricchiti con odds, aggiungiamo meta flag (senza alterare probabilities)
    enriched = any("odds_implied" in f for f in features)

    # Map feature enrichment back onto predictions (non modifichiamo prob)
    feat_map = {f["fixture_id"]: f for f in features if f.get("fixture_id") is not None}

    final_predictions = []
    for p in preds:
        fid = p.get("fixture_id")
            # Attach minimal odds context if enrichment available
        if enriched and fid in feat_map:
            f = feat_map[fid]
            attach: Dict[str, Any] = {}
            if "odds_original" in f:
                attach["odds_original"] = f["odds_original"]
            if "odds_implied" in f:
                attach["odds_implied"] = f["odds_implied"]
            if "odds_margin" in f:
                attach["odds_margin"] = f["odds_margin"]
            if attach:
                p["odds"] = attach
        final_predictions.append(p)

    payload = {
        "model_version": settings.model_baseline_version,
        "count": len(final_predictions),
        "enriched_with_odds": enriched,
        "predictions": final_predictions,
    }

    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    logger.info(
        "baseline_predictions_written",
        extra={"count": len(final_predictions), "model_version": settings.model_baseline_version, "enriched_odds": enriched},
    )


__all__ = ["run_baseline_predictions"]
