from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("predictions.value_alerts")

# Memorizza l’ultima soglia effettiva calcolata (dynamic threshold) per write_value_alerts
_LAST_EFFECTIVE_THRESHOLD: Optional[float] = None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _dynamic_factor(alerts_count: int) -> float:
    """
    Calcola fattore dinamico:
    - Se count > target => aumenta
    - Se count < target/2 => diminuisce
    Stateless: ricalcolato ad ogni run (semplice e robusto).
    """
    settings = get_settings()
    target = settings.value_alert_dynamic_target_count
    factor_min = settings.value_alert_dynamic_min_factor
    factor_max = settings.value_alert_dynamic_max_factor
    step = settings.value_alert_dynamic_adjust_step
    factor = 1.0
    if target > 0 and alerts_count > target:
        factor += step
    elif target > 0 and alerts_count < max(1, target // 2):
        factor -= step
    if factor < factor_min:
        factor = factor_min
    if factor > factor_max:
        factor = factor_max
    return factor


def build_value_alerts() -> List[Dict[str, Any]]:
    """
    Costruisce lista alert (prediction / consensus / merged opzionale).
    Applica soglia dinamica se abilitata.
    Ritorna SOLO la lista (compatibilità retroattiva).
    Dedup merged (prediction+consensus rimossi) se MERGED_DEDUP_ENABLE=1.
    """
    global _LAST_EFFECTIVE_THRESHOLD
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")

    base_threshold = settings.value_alert_min_edge

    preds = _load_predictions(base, settings.predictions_dir)
    consensus_entries = _load_consensus(base, settings.consensus_dir)

    # Conteggio per dynamic threshold (solo candidati attivi sopra base threshold)
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
        dynamic_factor = _dynamic_factor(prelim_count)
    else:
        dynamic_factor = 1.0

    effective_threshold = base_threshold * dynamic_factor
    _LAST_EFFECTIVE_THRESHOLD = effective_threshold  # salva per write_value_alerts

    alerts: List[Dict[str, Any]] = []
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
        for key, edge_pred in pred_index.items():
            if key in cons_index:
                fid, side = key
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

    # Dedup (se richiesto): se esiste merged per (fixture, side) rimuove prediction & consensus
    if settings.merged_dedup_enable and settings.enable_merged_value_alerts:
        merged_pairs = {
            (a.get("fixture_id"), a.get("value_side"))
            for a in alerts
            if a.get("source") == "merged"
        }
        if merged_pairs:
            alerts = [
                a
                for a in alerts
                if not (
                    a.get("source") in {"prediction", "consensus"}
                    and (a.get("fixture_id"), a.get("value_side")) in merged_pairs
                )
            ]

    return alerts


def write_value_alerts(alerts: List[Dict[str, Any]]) -> Optional[Path]:
    """
    Scrive value_alerts.json usando la soglia effettiva salvata (se presente).
    Compatibile con i test preesistenti (signature invariata).
    """
    settings = get_settings()
    if not settings.enable_value_alerts:
        logger.info("Value alerts disabilitati (ENABLE_VALUE_ALERTS=0).")
        return None

    base = Path(settings.bet_data_dir or "data")
    out_dir = base / settings.value_alerts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "value_alerts.json"

    effective_threshold = (
        _LAST_EFFECTIVE_THRESHOLD
        if _LAST_EFFECTIVE_THRESHOLD is not None
        else settings.value_alert_min_edge
    )
    dynamic_factor = (
        round(effective_threshold / settings.value_alert_min_edge, 6)
        if settings.value_alert_min_edge > 0
        else 1.0
    )

    payload = {
        "count": len(alerts),
        "threshold_edge": settings.value_alert_min_edge,
        "effective_threshold": effective_threshold,
        "dynamic_enabled": settings.value_alert_dynamic_enable,
        "dynamic_factor": dynamic_factor,
        "merged_enabled": settings.enable_merged_value_alerts,
        "merged_policy": (
            settings.merged_value_edge_policy
            if settings.enable_merged_value_alerts
            else None
        ),
        "dedup_merged": settings.merged_dedup_enable,
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
            "dedup_merged": settings.merged_dedup_enable,
        },
    )
    return target
