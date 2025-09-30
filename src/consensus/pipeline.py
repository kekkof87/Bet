from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("consensus.pipeline")


def _load_predictions_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura predictions file %s: %s", path, exc)
        return {}


def run_consensus_pipeline() -> Path:
    """
    Pipeline consensus stub:
      - Se ENABLE_CONSENSUS=0 → esce (ritorna path destinazione)
      - Carica predictions/latest_predictions.json
      - Per ogni prediction crea una voce consensus con:
          consensus_confidence = max(prob)
          ranking_score = prob.home_win - prob.away_win
      - Scrive consensus/consensus.json
    """
    settings = get_settings()
    base_dir = Path(settings.bet_data_dir or "data")
    pred_dir = base_dir / settings.predictions_dir
    cons_dir = base_dir / settings.consensus_dir
    cons_dir.mkdir(parents=True, exist_ok=True)
    target = cons_dir / "consensus.json"

    if not settings.enable_consensus:
        logger.info("Consensus disabilitato (ENABLE_CONSENSUS=0), skip.")
        return target

    predictions_path = pred_dir / "latest_predictions.json"
    preds_payload = _load_predictions_file(predictions_path)
    predictions = preds_payload.get("predictions") or []
    if not isinstance(predictions, list):
        predictions = []

    entries: List[Dict[str, Any]] = []
    for p in predictions:
        prob = p.get("prob") or {}
        try:
            hw = float(prob.get("home_win", 0))
            dr = float(prob.get("draw", 0))
            aw = float(prob.get("away_win", 0))
        except Exception:
            hw, dr, aw = 0.33, 0.34, 0.33
        consensus_conf = max(hw, dr, aw)
        ranking_score = hw - aw
        entries.append(
            {
                "fixture_id": p.get("fixture_id"),
                "prob": {"home_win": hw, "draw": dr, "away_win": aw},
                "consensus_confidence": round(consensus_conf, 4),
                "ranking_score": round(ranking_score, 4),
                "model_version": p.get("model_version"),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "model_sources": list({p.get("model_version") for p in predictions if p.get("model_version")}),
        "entries": entries,
    }

    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

    logger.info(
        "consensus_generated",
        extra={"count": len(entries), "model_sources": payload["model_sources"]},
    )
    return target


__all__ = ["run_consensus_pipeline"]
