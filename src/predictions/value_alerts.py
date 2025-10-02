# Versione aggiornata con dynamic threshold & effective_threshold.
# Sostituisci l'intero file.

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
    except Exception:
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
    except Exception:
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
    return max(pred_edge, cons_edge)

def _dynamic_factor(base_threshold: float, alerts_count: int) -> float:
    """
    Calcola fattore dinamico semplice:
    Se count > target => incrementa,
    Se count < target/2 => decrementa,
    Clamp tra min_factor e max_factor.
    """
    settings = get_settings()
    target = settings.value_alert_dynamic_target_count
    factor_min = settings.value_alert_dynamic_min_factor
    factor_max = settings.value_alert_dynamic_max_factor
    step = settings.value_alert_dynamic_adjust_step
    # Recupera ultimo fattore da file se esiste (persistenza leggera)
    # (Per semplicità NON persistiamo: stateless -> calcolo reattivo a conteggio corrente)
    factor = 1.0
    if alerts_count > target and target > 0:
        factor += step
    elif alerts_count < max(1, target // 2):
        factor -= step
    if factor < factor_min:
        factor = factor_min
    if factor > factor_max:
        factor = factor_max
    return factor

def build_value_alerts() -> List[Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    alerts: List[Dict[str, Any]] = []
    base_threshold = settings.value_alert_min_edge

    preds = _load_predictions(base, settings.predictions_dir)
    consensus_entries = _load_consensus(base, settings.consensus_dir)

    # Conteggio preliminare per dynamic threshold (prediction + consensus attivi)
    if settings.value_alert_dynamic_enable:
        prelim_count = 0
        for p in preds:
            vb = p.get("value")
            if isinstance(vb, dict) and vb.get("active") is True:
                try:
                    edge = float(vb.get("value_edge", 0.0))
                except Exception:
                    continue
                if edge >= base_threshold:
                    prelim_count += 1
        for c in consensus_entries:
            cv = c.get("consensus_value")
            if isinstance(cv, dict) and cv.get("active") is True:
                try:
                    edge = float(cv.get("value_edge", 0.0))
                except Exception:
                    continue
                if edge >= base_threshold:
                    prelim_count += 1
        dynamic_factor = _dynamic_factor(base_threshold, prelim_count)
    else:
        dynamic_factor = 1.0

    effective_threshold = base_threshold * dynamic_factor

    pred_index: Dict[Tuple[int, str], float] = {}
    cons_index: Dict[Tuple[int, str], float] = {}

    # Prediction alerts
    for p in preds:
        vb = p.get("value")
        if not isinstance(vb, dict):
            continue
        if vb.get("active") is True:
            try:
                edge_f = float(vb.get("value_edge"))
            except Exception:
                continue
            if edge_f < effective_threshold:
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
                pred_index[(fid, side)] = edge_f

    # Consensus alerts
    for c in consensus_entries:
        cv = c.get("consensus_value")
        if not isinstance(cv, dict):
            continue
        if cv.get("active") is True:
            try:
                edge_f = float(cv.get("value_edge"))
            except Exception:
                continue
            if edge_f < effective_threshold:
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
                cons_index[(fid, side)] = edge_f

    # Merged
    if settings.enable_merged_value_alerts:
        policy = settings.merged_value_edge_policy
        for key, e_pred in pred_index.items():
            if key in cons_index:
                fid, side = key
                edge_pred = e_pred
                edge_cons = cons_index[key]
                merged_edge = _policy_edge(edge_pred, edge_cons, policy)
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

    return alerts, effective_threshold

def write_value_alerts(alerts_with_threshold) -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_value_alerts:
        logger.info("Value alerts disabilitati (ENABLE_VALUE_ALERTS=0).")
        return None
    alerts, effective_threshold = alerts_with_threshold
    base = Path(settings.bet_data_dir or "data")
    out_dir = base / settings.value_alerts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "value_alerts.json"

    payload = {
        "count": len(alerts),
        "threshold_edge": settings.value_alert_min_edge,
        "effective_threshold": effective_threshold,
        "dynamic_enabled": settings.value_alert_dynamic_enable,
        "dynamic_factor": round(effective_threshold / settings.value_alert_min_edge, 6)
        if settings.value_alert_min_edge > 0 else 1.0,
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
            "effective_threshold": effective_threshold,
            "dynamic": settings.value_alert_dynamic_enable,
        },
    )
    return target
