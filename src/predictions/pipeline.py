from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from core.config import get_settings
from core.logging import get_logger
from .features import build_features
from .model import BaselineModel

logger = get_logger("predictions.pipeline")


def run_baseline_predictions(fixtures: List[Dict[str, Any]]) -> Path:
    """
    Esegue pipeline baseline:
      1. Estrae feature
      2. Carica modello baseline
      3. Genera predictions
      4. Salva predictions/latest_predictions.json
    Ritorna il path del file (anche se disabilitato restituisce percorso dove sarebbe).
    """
    settings = get_settings()
    base_dir = Path(settings.bet_data_dir or "data")
    pred_dir = base_dir / settings.predictions_dir
    pred_dir.mkdir(parents=True, exist_ok=True)

    if not settings.enable_predictions:
        logger.info("Predictions disabilitate (ENABLE_PREDICTIONS=0), skip.")
        return pred_dir / "latest_predictions.json"

    feats = build_features(fixtures)
    model = BaselineModel(version=settings.model_baseline_version)
    preds = model.predict(feats)

    payload = {
        "model_version": settings.model_baseline_version,
        "count": len(preds),
        "predictions": preds,
    }

    target = pred_dir / "latest_predictions.json"
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    logger.info("predictions_generated", extra={"count": len(preds), "model_version": settings.model_baseline_version})
    return target


__all__ = ["run_baseline_predictions"]
