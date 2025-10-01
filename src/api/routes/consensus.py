from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("api.routes.consensus")
router = APIRouter(prefix="/consensus", tags=["consensus"])


def _load_consensus() -> Optional[Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    f = base / settings.consensus_dir / "consensus.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura consensus: %s", exc)
        raise HTTPException(status_code=500, detail="failed to read consensus") from exc


@router.get("", summary="Consensus entries con filtri opzionali")
def list_consensus(
    min_confidence: Optional[float] = Query(None, ge=0, le=1, description="Min consensus_confidence"),
    min_value_edge: Optional[float] = Query(None, ge=0, le=1, description="Min consensus_value.value_edge"),
    value_only: bool = Query(False, description="Solo entries con consensus_value.active=true"),
    limit: Optional[int] = Query(None, ge=1, le=500),
):
    data = _load_consensus()
    if not data:
        return {
            "count": 0,
            "total_available": 0,
            "items": [],
            "detail": "consensus file not found",
        }
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise HTTPException(status_code=500, detail="invalid consensus payload")

    def is_active_value(e: Dict[str, Any]) -> bool:
        cv = e.get("consensus_value")
        return isinstance(cv, dict) and cv.get("active") is True

    def value_edge(e: Dict[str, Any]) -> float:
        cv = e.get("consensus_value")
        if not isinstance(cv, dict):
            return float("-inf")
        return float(cv.get("value_edge", float("-inf")))

    filtered = entries

    if value_only:
        filtered = [e for e in filtered if is_active_value(e)]
    if min_confidence is not None:
        filtered = [e for e in filtered if float(e.get("consensus_confidence", 0.0)) >= min_confidence]
    if min_value_edge is not None:
        filtered = [e for e in filtered if is_active_value(e) and value_edge(e) >= min_value_edge]

    value_filtered = value_only or (min_value_edge is not None)
    if value_filtered:
        filtered.sort(key=lambda e: value_edge(e), reverse=True)
    else:
        filtered.sort(key=lambda e: e.get("fixture_id") or 0)

    total = len(entries)
    if limit is not None:
        filtered = filtered[:limit]

    return {
        "count": len(filtered),
        "total_available": total,
        "value_filtered": value_filtered,
        "items": filtered,
        "baseline_weight": data.get("baseline_weight"),
    }
