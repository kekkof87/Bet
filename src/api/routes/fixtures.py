from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["fixtures"])
logger = get_logger("api.routes.fixtures")


@router.get("/fixtures", summary="Lista fixtures correnti")
def get_fixtures():
    """
    Se il file non esiste: ritorna [] (il test si aspetta proprio una lista vuota).
    Se esiste ma payload non valido: lista vuota.
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / "fixtures_latest.json"
    if not fpath.exists():
        return []
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura fixtures_latest.json: %s", exc)
        return []
