from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def build_value_alerts() -> List[Dict[str, Any]]:
    """
    Crea lista unificata di alert 'value':
    - source: prediction | consensus
    - value_type: prediction_value | consensus_value
    - edge, side, fixture_id
    Applica filtro edge >= settings.value_alert_min_edge
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    alerts: List[Dict[str, Any]] = []
    threshold = settings.value_alert_min_edge

    preds = _load_predictions(base, settings.predictions_dir)
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
            alerts.append(
                {
                    "source": "prediction",
                    "value_type": "prediction_value",
                    "fixture_id": p.get("fixture_id"),
                    "value_side": vb.get("value_side"),
                    "value_edge": edge_f,
                    "deltas": vb.get("deltas"),
                    "model_version": p.get("model_version"),
                }
            )

    consensus_entries = _load_consensus(base, settings.consensus_dir)
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
            alerts.append(
                {
                    "source": "consensus",
                    "value_type": "consensus_value",
                    "fixture_id": c.get("fixture_id"),
                    "value_side": cv.get("value_side"),
                    "value_edge": edge_f,
                    "deltas": cv.get("deltas"),
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
        "alerts": alerts,
    }
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    logger.info("value_alerts_written", extra={"count": len(alerts), "threshold": settings.value_alert_min_edge})

    return target
