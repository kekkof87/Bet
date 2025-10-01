from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("api.routes.value_alerts")
router = APIRouter(prefix="/value_alerts", tags=["value-alerts"])


def _load_value_alerts() -> Optional[Dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_value_alerts:
        return None
    base = Path(settings.bet_data_dir or "data")
    fpath = base / settings.value_alerts_dir / "value_alerts.json"
    if not fpath.exists():
        return None
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura value_alerts: %s", exc)
        return None


@router.get("", summary="Value alerts attivi (prediction + consensus)")
def list_value_alerts(
    source: Optional[List[str]] = Query(
        default=None,
        description="Filtra sorgenti (prediction, consensus). Parametro ripetibile.",
    ),
    min_edge: Optional[float] = Query(
        default=None, ge=0, le=1, description="Soglia minima value_edge"
    ),
    limit: Optional[int] = Query(
        default=None, ge=1, le=500, description="Limite record (max 500)"
    ),
):
    """
    Ritorna gli alert di value generati (prediction_value / consensus_value).
    Filtri:
      - source: uno o più tra prediction, consensus
      - min_edge: value_edge >= soglia
      - limit: taglia elenco finale
    Ordinamento:
      - Se min_edge applicato: value_edge desc
      - Altrimenti fixture_id asc (se presente) e poi source
    """
    raw = _load_value_alerts()
    if not raw:
        return {
            "count": 0,
            "total_available": 0,
            "items": [],
            "filters": {
                "sources": source or [],
                "min_edge": min_edge,
                "limit": limit,
            },
            "detail": "value alerts file not found or disabled",
        }

    alerts = raw.get("alerts")
    if not isinstance(alerts, list):
        return {
            "count": 0,
            "total_available": 0,
            "items": [],
            "filters": {
                "sources": source or [],
                "min_edge": min_edge,
                "limit": limit,
            },
            "detail": "invalid alerts payload",
        }

    total = len(alerts)
    filtered = alerts

    # Normalizziamo sorgenti richieste
    if source:
        wanted = {s.lower() for s in source}
        filtered = [a for a in filtered if str(a.get("source")).lower() in wanted]

    if min_edge is not None:
        filtered = [
            a
            for a in filtered
            if isinstance(a.get("value_edge"), (int, float))
            and float(a["value_edge"]) >= min_edge
        ]

    value_filter_applied = min_edge is not None

    # Ordinamento
    if value_filter_applied:
        filtered.sort(
            key=lambda a: float(a.get("value_edge", float("-inf"))), reverse=True
        )
    else:
        filtered.sort(
            key=lambda a: (
                a.get("fixture_id") if isinstance(a.get("fixture_id"), int) else 0,
                str(a.get("source")),
            )
        )

    if limit is not None:
        filtered = filtered[:limit]

    return {
        "count": len(filtered),
        "total_available": total,
        "filters": {
            "sources": source or [],
            "min_edge": min_edge,
            "limit": limit,
        },
        "items": filtered,
        "value_filter_applied": value_filter_applied,
    }
