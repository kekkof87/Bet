from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["scoreboard"])
logger = get_logger("api.routes.scoreboard")


@router.get("/scoreboard", summary="Scoreboard sintetico")
def get_scoreboard():
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    fpath = base / "scoreboard.json"
    if not fpath.exists():
        return {
            "total": 0,
            "live_count": 0,
            "upcoming_count_next_24h": 0,
            "recent_delta": {"added": 0, "removed": 0, "modified": 0},
            "change_breakdown": {
                "score_change": 0,
                "status_change": 0,
                "both": 0,
                "other": 0,
            },
            "live_fixtures": [],
            "upcoming_next_24h": [],
            "last_fetch_total_new": 0,
            "detail": "scoreboard file not found",
        }
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura scoreboard.json: %s", exc)
        return {
            "total": 0,
            "live_count": 0,
            "upcoming_count_next_24h": 0,
            "recent_delta": {"added": 0, "removed": 0, "modified": 0},
            "change_breakdown": {
                "score_change": 0,
                "status_change": 0,
                "both": 0,
                "other": 0,
            },
            "live_fixtures": [],
            "upcoming_next_24h": [],
            "last_fetch_total_new": 0,
            "detail": "read error",
        }
