from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from core.config import get_settings
from core.logging import get_logger
from predictions.features import build_features
from predictions.model import BaselineModel

logger = get_logger("predictions.pipeline")


def run_baseline_predictions(fixtures: List[Dict]) -> Path:
    """
    Esegue la pipeline baseline:
      - Se ENABLE_PREDICTIONS=0 → crea cartella (se serve) ma non scrive file (skip)
      - Altrimenti genera predictions/latest_predictions.json
    """
    settings = get_settings()
    base_dir = Path(settings.bet_data_dir or "data")
    pred_dir = base_dir / settings.predictions_dir
    pred_dir.mkdir(parents=True, exist_ok=True)
    target = pred_dir / "latest_predictions.json"

    if not settings.enable_predictions:
        logger.info("Predictions disabilitate: skip generazione.")
        return target

    feats = build_features(fixtures)
    model = BaselineModel(version=settings.model_baseline_version)
    preds = model.predict(feats)

    payload = {
        "model_version": settings.model_baseline_version,
        "count": len(preds),
        "predictions": preds,
    }
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    logger.info(
        "predictions_generated",
        extra={"count": len(preds), "model_version": settings.model_baseline_version},
    )
    return target


__all__ = ["run_baseline_predictions"]
