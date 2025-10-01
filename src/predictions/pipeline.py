from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_settings
from core.logging import get_logger
from predictions.features import build_features
from predictions.model import BaselineModel

logger = get_logger("predictions.pipeline")


def run_baseline_predictions(fixtures: List[Dict[str, Any]]) -> Optional[Path]:
    """
    Esegue la baseline prediction pipeline:
    - build features (+ odds enrichment opzionale)
    - inferenza modello baseline
    - allega blocco odds (se enrichment presente)
    - scrive latest_predictions.json
    Ritorna il Path del file scritto (o None se disabilitato).
    """
    settings = get_settings()
    if not settings.enable_predictions:
        logger.info("Predictions disabilitate (ENABLE_PREDICTIONS=0)")
        return None

    base = Path(settings.bet_data_dir or "data")
    p_dir = base / settings.predictions_dir
    p_dir.mkdir(parents=True, exist_ok=True)
    target = p_dir / "latest_predictions.json"

    features = build_features(fixtures)
    model = BaselineModel(version=settings.model_baseline_version)
    preds = model.predict(features)

    enriched = any("odds_implied" in f for f in features)
    feat_map = {f["fixture_id"]: f for f in features if f.get("fixture_id") is not None}

    final_predictions: List[Dict[str, Any]] = []
    for pred in preds:
        fid = pred.get("fixture_id")
        if enriched and fid in feat_map:
            fdata = feat_map[fid]
            attach: Dict[str, Any] = {}
            if "odds_original" in fdata:
                attach["odds_original"] = fdata["odds_original"]
            if "odds_implied" in fdata:
                attach["odds_implied"] = fdata["odds_implied"]
            if "odds_margin" in fdata:
                attach["odds_margin"] = fdata["odds_margin"]
            if attach:
                pred["odds"] = attach
        final_predictions.append(pred)

    payload: Dict[str, Any] = {
        "model_version": settings.model_baseline_version,
        "count": len(final_predictions),
        "enriched_with_odds": enriched,
        "predictions": final_predictions,
    }

    tmp_file = target.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp_file, target)

    logger.info(
        "baseline_predictions_written",
        extra={
            "count": len(final_predictions),
            "model_version": settings.model_baseline_version,
            "enriched_odds": enriched,
        },
    )
    return target


__all__ = ["run_baseline_predictions"]
