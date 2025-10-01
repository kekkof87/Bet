from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["metrics"])
logger = get_logger("api.routes.metrics")


@router.get("/metrics", summary="Ultima snapshot metrics")
def get_metrics():
    """
    Ritorna il contenuto di metrics/last_run.json.
    Se il file non esiste -> 404.
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / settings.metrics_dir / "last_run.json"
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="metrics file not found")
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise HTTPException(status_code=500, detail="invalid metrics payload")
        return data
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura last_run.json: %s", exc)
        raise HTTPException(status_code=500, detail="failed to read metrics")
