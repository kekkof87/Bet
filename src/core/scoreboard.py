from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging import get_logger
from core.config import get_settings

logger = get_logger("core.scoreboard")

_LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "LIVE"}  # Puoi estendere
# Se vuoi escludere FT dai live, non inserirlo; se vuoi includere stato finale differenzia in futuro.


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # Gestione rapida di formati ISO varianti
    try:
        # Python 3.11 isoformat parsing robusto
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except Exception:
        return None


def build_scoreboard(
    fixtures: List[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
    delta: Optional[Dict[str, Any]],
    *,
    upcoming_window_hours: int = 24,
    limit_lists: int = 10,
) -> Dict[str, Any]:
    """
    Crea uno scoreboard aggregato con subset di informazioni per consumo rapido.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=upcoming_window_hours)

    total = len(fixtures)

    live = []
    upcoming = []
    for f in fixtures:
        status = f.get("status")
        if status in _LIVE_STATUSES:
            live.append(f)
            continue
        dt = _parse_dt(f.get("date_utc"))
            # FT non incluso in live per design attuale
        if dt and now <= dt <= horizon and status == "NS":
            upcoming.append(f)

    live_count = len(live)
    upcoming_count = len(upcoming)

    change_breakdown = {}
    recent_delta_counts = {"added": 0, "removed": 0, "modified": 0}

    if delta:
        recent_delta_counts["added"] = len(delta.get("added", []))
        recent_delta_counts["removed"] = len(delta.get("removed", []))
        recent_delta_counts["modified"] = len(delta.get("modified", []))
        cb = delta.get("change_breakdown")
        if isinstance(cb, dict):
            change_breakdown = cb

    if not change_breakdown and metrics:
        change_breakdown = metrics.get("change_breakdown", {}) or {}

    scoreboard = {
        "generated_at": now.isoformat(),
        "total": total,
        "live_count": live_count,
        "upcoming_count_next_24h": upcoming_count,
        "recent_delta": recent_delta_counts,
        "change_breakdown": change_breakdown,
        "live_fixtures": live[:limit_lists],
        "upcoming_next_24h": upcoming[:limit_lists],
    }

    if metrics:
        scoreboard["last_fetch_total_new"] = metrics.get("summary", {}).get("total_new")

    return scoreboard


def write_scoreboard(scoreboard: Dict[str, Any]) -> Path:
    """
    Scrive scoreboard.json nella BET_DATA_DIR root.
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    base.mkdir(parents=True, exist_ok=True)
    target = base / "scoreboard.json"
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(scoreboard, f, ensure_ascii=False, indent=2)
    tmp.replace(target)
    return target
