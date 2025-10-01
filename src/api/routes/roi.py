from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Query

from core.config import get_settings
from core.logging import get_logger
from analytics.roi import load_roi_summary, load_roi_ledger

logger = get_logger("api.routes.roi")

router = APIRouter(prefix="/roi", tags=["roi"])


@router.get("", summary="ROI summary e (opz.) picks ledger")
def roi_summary(
    detail: bool = Query(False, description="Se true include elenco picks (limit filtrato)"),
    source: Optional[List[str]] = Query(
        default=None,
        description="Filtra picks per source (prediction, consensus) - parametro ripetibile",
    ),
    open_only: bool = Query(False, description="Mostra solo picks aperte (se detail=true)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limite picks in elenco"),
):
    settings = get_settings()
    if not settings.enable_roi_tracking:
        return {
            "enabled": False,
            "detail": False,
            "metrics": None,
            "items": [],
            "filters": {},
            "detail_included": False,
        }

    metrics = load_roi_summary()
    if not metrics:
        return {
            "enabled": True,
            "detail": False,
            "metrics": None,
            "items": [],
            "filters": {},
            "detail_included": False,
            "message": "metrics not available yet",
        }

    items = []
    detail_included = False
    chosen_sources = [s.lower() for s in source] if source else None

    if detail:
        ledger = load_roi_ledger()
        filtered = ledger
        if chosen_sources:
            filtered = [p for p in filtered if str(p.get("source")).lower() in chosen_sources]
        if open_only:
            filtered = [p for p in filtered if p.get("settled") is False]
        # Ordina per created_at
        filtered.sort(key=lambda p: p.get("created_at") or "")
        if limit is not None:
            filtered = filtered[:limit]
        items = filtered
        detail_included = True

    return {
        "enabled": True,
        "detail": detail,
        "metrics": metrics,
        "items": items,
        "filters": {
            "sources": chosen_sources or [],
            "open_only": open_only,
            "limit": limit,
        },
        "detail_included": detail_included,
    }
