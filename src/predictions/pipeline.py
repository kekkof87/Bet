from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import get_settings
from core.logging import get_logger
from predictions.features import build_features
from predictions.model import BaselineModel
from predictions.value import compute_value_block

logger = get_logger("predictions.pipeline")


def _blend_adjust(
    base_prob: Dict[str, float],
    odds_implied: Dict[str, float],
    weight: float,
) -> Dict[str, float]:
    keys = ["home_win", "draw", "away_win"]
    w = max(0.0, min(1.0, weight))
    w_market = 1.0 - w
    out: Dict[str, float] = {}
    for k in keys:
        pb = float(base_prob.get(k, 0.0))
        pi = float(odds_implied.get(k, pb))
        out[k] = w * pb + w_market * pi
    s = sum(out.values())
    if s > 0:
        for k in keys:
            out[k] = out[k] / s
    return {k: round(v, 6) for k, v in out.items()}


def run_baseline_predictions(fixtures: List[Dict[str, Any]]) -> Optional[Path]:
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

    enriched_odds = any("odds_implied" in f for f in features)
    feat_map = {f["fixture_id"]: f for f in features if f.get("fixture_id") is not None}
    model_adjust_applied = settings.enable_model_adjust and enriched_odds

    final_predictions: List[Dict[str, Any]] = []
    for pred in preds:
        fid = pred.get("fixture_id")
        if enriched_odds and fid in feat_map:
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
                # Value detection
                if "odds_implied" in attach:
                    vb = compute_value_block(
                        pred.get("prob", {}),
                        attach["odds_implied"],
                        attach.get("odds_margin"),
                    )
                    if vb:
                        pred["value"] = vb
                # Model adjust
                if model_adjust_applied and "odds_implied" in attach:
                    try:
                        pred["prob_adjusted"] = _blend_adjust(
                            pred.get("prob", {}),
                            attach["odds_implied"],
                            settings.model_adjust_weight,
                        )
                    except Exception:  # pragma: no cover
                        pass
        final_predictions.append(pred)

    payload: Dict[str, Any] = {
        "model_version": settings.model_baseline_version,
        "count": len(final_predictions),
        "enriched_with_odds": enriched_odds,
        "value_detection": settings.enable_value_detection,
        "model_adjust_enabled": settings.enable_model_adjust,
        "model_adjust_weight": settings.model_adjust_weight if settings.enable_model_adjust else None,
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
            "enriched_odds": enriched_odds,
            "value_detection": settings.enable_value_detection,
            "model_adjust": model_adjust_applied,
        },
    )
    return target


__all__ = ["run_baseline_predictions"]
