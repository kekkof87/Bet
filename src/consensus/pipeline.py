from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("consensus.pipeline")


def _load_predictions(base: Path, predictions_dir: str) -> List[Dict[str, Any]]:
    f = base / predictions_dir / "latest_predictions.json"
    if not f.exists():
        logger.info("Predictions file non trovato per consensus.")
        return []
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura predictions file: %s", exc)
        return []
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for p in preds:
        if not isinstance(p, dict):
            continue
        if "fixture_id" not in p:
            continue
        cleaned.append(p)
    return cleaned


def _blend_probs(
    baseline_prob: Dict[str, float],
    odds_implied: Optional[Dict[str, float]],
    w_baseline: float,
) -> Dict[str, float]:
    keys = ["home_win", "draw", "away_win"]
    blended: Dict[str, float] = {}
    if not odds_implied:
        # solo baseline
        for k in keys:
            blended[k] = float(baseline_prob.get(k, 0.0))
        return blended
    w_market = 1.0 - w_baseline
    for k in keys:
        pb = float(baseline_prob.get(k, 0.0))
        pi = float(odds_implied.get(k, pb))  # fallback baseline se manca
        blended[k] = w_baseline * pb + w_market * pi
    # normalizzazione di sicurezza
    s = sum(blended.values())
    if s > 0:
        for k in keys:
            blended[k] = blended[k] / s
    return blended


def _consensus_value_signal(blended: Dict[str, float], odds_implied: Optional[Dict[str, float]]) -> Optional[Dict[str, Any]]:
    if not odds_implied:
        return None
    deltas: Dict[str, float] = {}
    for k in ["home_win", "draw", "away_win"]:
        deltas[k] = blended.get(k, 0.0) - float(odds_implied.get(k, 0.0))
    side = max(deltas, key=lambda x: deltas[x])
    edge = deltas[side]
    if edge <= 0:
        return {
            "active": False,
            "value_side": side,
            "value_edge": round(edge, 6),
            "deltas": {k: round(v, 6) for k, v in deltas.items()},
        }
    return {
        "active": True,
        "value_side": side,
        "value_edge": round(edge, 6),
        "deltas": {k: round(v, 6) for k, v in deltas.items()},
    }


def run_consensus_pipeline() -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_consensus:
        logger.info("Consensus disabilitato (ENABLE_CONSENSUS=0)")
        return None

    base = Path(settings.bet_data_dir or "data")
    out_dir = base / settings.consensus_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "consensus.json"

    predictions = _load_predictions(base, settings.predictions_dir)
    if not predictions:
        payload = {
            "generated_at": None,
            "count": 0,
            "model_sources": [],
            "entries": [],
            "baseline_weight": settings.consensus_baseline_weight,
        }
        tmp = target.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
        logger.info("Consensus scritto (vuoto).")
        return target

    entries: List[Dict[str, Any]] = []
    w = settings.consensus_baseline_weight

    for p in predictions:
        fid = p.get("fixture_id")
        prob = p.get("prob") or {}
        odds_block = p.get("odds") or {}
        odds_implied = odds_block.get("odds_implied")
        blended = _blend_probs(prob, odds_implied, w)
        consensus_conf = max(blended.values()) if blended else 0.0
        ranking_score = blended.get("home_win", 0.0) - blended.get("away_win", 0.0)
        value_sig = _consensus_value_signal(blended, odds_implied)

        entry = {
            "fixture_id": fid,
            "blended_prob": {k: round(v, 6) for k, v in blended.items()},
            "consensus_confidence": round(consensus_conf, 6),
            "ranking_score": round(ranking_score, 6),
        }
        if value_sig:
            entry["consensus_value"] = value_sig
        entry["model_version"] = p.get("model_version")
        entries.append(entry)

    payload = {
        "generated_at": entries and entries[0].get("fixture_id"),
        "count": len(entries),
        "model_sources": [settings.model_baseline_version],
        "baseline_weight": w,
        "entries": entries,
    }

    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    logger.info(
        "Consensus scritto",
        extra={"count": len(entries), "baseline_weight": w},
    )
    return target


__all__ = ["run_consensus_pipeline"]
