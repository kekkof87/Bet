from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("predictions.value_alerts")


def _load_predictions(base: Path, predictions_dir: str) -> List[Dict[str, Any]]:
    f = base / predictions_dir / "latest_predictions.json"
    if not f.exists():
        return []
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return []
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        return []
    return [p for p in preds if isinstance(p, dict)]


def _load_consensus(base: Path, consensus_dir: str) -> List[Dict[str, Any]]:
    f = base / consensus_dir / "consensus.json"
    if not f.exists():
        return []
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return []
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def _policy_edge(pred_edge: float, cons_edge: float, policy: str) -> float:
    if policy == "min":
        return min(pred_edge, cons_edge)
    if policy == "avg":
        return (pred_edge + cons_edge) / 2.0
    return max(pred_edge, cons_edge)  # default max


def build_value_alerts() -> List[Dict[str, Any]]:
    """
    Costruisce lista alert:
      - prediction_value
      - consensus_value
      - (opzionale) merged_value (se entrambi attivi stesso fixture+side)
    Applica threshold settings.value_alert_min_edge a ciascun edge.
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    alerts: List[Dict[str, Any]] = []
    threshold = settings.value_alert_min_edge

    # Prediction alerts
    preds = _load_predictions(base, settings.predictions_dir)
    pred_index: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for p in preds:
        vb = p.get("value")
        if not isinstance(vb, dict):
            continue
        if vb.get("active") is True:
            edge = vb.get("value_edge")
            try:
                edge_f = float(edge)
            except Exception:
                continue
            if edge_f < threshold:
                continue
            side = vb.get("value_side")
            fid = p.get("fixture_id")
            alerts.append(
                {
                    "source": "prediction",
                    "value_type": "prediction_value",
                    "fixture_id": fid,
                    "value_side": side,
                    "value_edge": edge_f,
                    "deltas": vb.get("deltas"),
                    "model_version": p.get("model_version"),
                }
            )
            if isinstance(fid, int) and isinstance(side, str):
                pred_index[(fid, side)] = {"edge": edge_f}

    # Consensus alerts
    consensus_entries = _load_consensus(base, settings.consensus_dir)
    cons_index: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for c in consensus_entries:
        cv = c.get("consensus_value")
        if not isinstance(cv, dict):
            continue
        if cv.get("active") is True:
            edge = cv.get("value_edge")
            try:
                edge_f = float(edge)
            except Exception:
                continue
            if edge_f < threshold:
                continue
            side = cv.get("value_side")
            fid = c.get("fixture_id")
            alerts.append(
                {
                    "source": "consensus",
                    "value_type": "consensus_value",
                    "fixture_id": fid,
                    "value_side": side,
                    "value_edge": edge_f,
                    "deltas": cv.get("deltas"),
                }
            )
            if isinstance(fid, int) and isinstance(side, str):
                cons_index[(fid, side)] = {"edge": edge_f}

    # Merged (optional)
    if settings.enable_merged_value_alerts:
        policy = settings.merged_value_edge_policy
        for key, p_info in pred_index.items():
            if key in cons_index:
                fid, side = key
                edge_pred = p_info["edge"]
                edge_cons = cons_index[key]["edge"]
                merged_edge = _policy_edge(edge_pred, edge_cons, policy)
                # soglia già superata da entrambi, quindi merged_edge sarà >= threshold se policy=max/avg/min coerente
                alerts.append(
                    {
                        "source": "merged",
                        "value_type": "merged_value",
                        "fixture_id": fid,
                        "value_side": side,
                        "value_edge": round(merged_edge, 6),
                        "components": {
                            "prediction_edge": edge_pred,
                            "consensus_edge": edge_cons,
                            "policy": policy,
                        },
                    }
                )

    return alerts


def write_value_alerts(alerts: List[Dict[str, Any]]) -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_value_alerts:
        logger.info("Value alerts disabilitati (ENABLE_VALUE_ALERTS=0).")
        return None
    base = Path(settings.bet_data_dir or "data")
    out_dir = base / settings.value_alerts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "value_alerts.json"

    payload = {
        "count": len(alerts),
        "threshold_edge": settings.value_alert_min_edge,
        "merged_enabled": settings.enable_merged_value_alerts,
        "merged_policy": settings.merged_value_edge_policy if settings.enable_merged_value_alerts else None,
        "alerts": alerts,
    }
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    logger.info(
        "value_alerts_written",
        extra={
            "count": len(alerts),
            "threshold": settings.value_alert_min_edge,
            "merged": settings.enable_merged_value_alerts,
        },
    )
    return target
