from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("api.routes.predictions")

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _load_predictions() -> Optional[Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / settings.predictions_dir / "latest_predictions.json"
    if not fpath.exists():
        return None
    try:
        import json

        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura predictions file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read predictions file") from exc


@router.get("", summary="Lista predictions con filtri opzionali")
def list_predictions(
    value_only: bool = Query(False, description="Mostra solo predictions con value.active == true"),
    min_edge: Optional[float] = Query(
        None, ge=0, le=1, description="Soglia minima per value_edge (considera solo predictions con value)"
    ),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Limite max risultati (default: nessun limite)"),
):
    """
    Ritorna le predictions dal file latest_predictions.json.

    Filtri:
    - value_only: include solo predictions con blocco value attivo
    - min_edge: se fornito, include solo predictions con value_edge >= min_edge
    - limit: taglia il numero di elementi finali

    Ordinamento:
    - Se value_only o min_edge: value_edge desc
    - Altrimenti: fixture_id asc

    Se il file non esiste: ritorna lista vuota (non 404) per semplicità di consumo.
    """
    data = _load_predictions()
    if not data:
        return {
            "model_version": None,
            "count": 0,
            "total_available": 0,
            "value_only": value_only,
            "min_edge": min_edge,
            "value_filtered": False,
            "items": [],
            "detail": "predictions file not found",
        }

    model_version = data.get("model_version")
    preds = data.get("predictions")
    if not isinstance(preds, list):
        raise HTTPException(status_code=500, detail="Invalid predictions payload")

    total_available = len(preds)
    value_filtered = False

    # Funzione per estrarre edge (anche se non attivo)
    def edge_of(p: Dict[str, Any]) -> float:
        v = p.get("value")
        if not isinstance(v, dict):
            return float("-inf")
        return float(v.get("value_edge", float("-inf")))

    def active_value(p: Dict[str, Any]) -> bool:
        v = p.get("value")
        return isinstance(v, dict) and v.get("active") is True

    filtered: List[Dict[str, Any]] = preds

    if value_only:
        filtered = [p for p in filtered if active_value(p)]
        value_filtered = True

    if min_edge is not None:
        # Applichiamo la soglia solo a predictions con value block; le altre vengono escluse
        before = len(filtered)
        filtered = [p for p in filtered if active_value(p) and edge_of(p) >= min_edge]
        if before != len(filtered):
            value_filtered = True

    # Ordinamento
    if value_filtered:
        filtered.sort(key=lambda p: edge_of(p), reverse=True)
    else:
        filtered.sort(key=lambda p: p.get("fixture_id") or 0)

    # Limit
    if limit is not None:
        filtered = filtered[:limit]

    return {
        "model_version": model_version,
        "count": len(filtered),
        "total_available": total_available,
        "value_only": value_only,
        "min_edge": min_edge,
        "value_filtered": value_filtered,
        "items": filtered,
    }
