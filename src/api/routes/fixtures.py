from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["fixtures"])
logger = get_logger("api.routes.fixtures")


@router.get("/fixtures", summary="Lista fixtures correnti")
def get_fixtures():
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / "fixtures_latest.json"
    if not fpath.exists():
        return {
            "count": 0,
            "items": [],
            "detail": "fixtures file not found",
        }
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return {"count": 0, "items": [], "detail": "invalid fixtures payload"}
        return {
            "count": len(data),
            "items": data,
        }
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura fixtures_latest.json: %s", exc)
        return {"count": 0, "items": [], "detail": "read error"}
