from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["scoreboard"])
logger = get_logger("api.routes.scoreboard")


@router.get("/scoreboard", summary="Scoreboard sintetico")
def get_scoreboard():
    """
    Se il file manca -> 404 (test si aspetta 404).
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / "scoreboard.json"
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="scoreboard file not found")
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura scoreboard.json: %s", exc)
        raise HTTPException(status_code=500, detail="failed to read scoreboard")
