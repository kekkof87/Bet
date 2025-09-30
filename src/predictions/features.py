from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LIVE_STATUSES = {"1H", "HT", "2H", "ET", "LIVE", "AET", "P"}


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def build_features(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Feature basilari per baseline:
      - is_live
      - score_diff
      - hours_to_kickoff (se NS futura)
      - status_code (assegnato dinamicamente)
    """
    out: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    status_map: Dict[str, int] = {}
    next_code = 1

    def status_code(st: Optional[str]) -> int:
        nonlocal next_code
        if not st:
            return 0
        if st not in status_map:
            status_map[st] = next_code
            next_code += 1
        return status_map[st]

    for fx in fixtures:
        st = fx.get("status")
        is_live = st in _LIVE_STATUSES
        hs = fx.get("home_score")
        as_ = fx.get("away_score")
        try:
            score_diff = int(hs) - int(as_) if hs is not None and as_ is not None else 0
        except Exception:
            score_diff = 0

        dt = _parse_dt(fx.get("date_utc"))
        hours_to_kickoff = None
        if st == "NS" and dt:
            hours_to_kickoff = round((dt - now).total_seconds() / 3600.0, 3)

        out.append(
            {
                "fixture_id": fx.get("fixture_id"),
                "is_live": is_live,
                "score_diff": score_diff,
                "status": st,
                "status_code": status_code(st),
                "hours_to_kickoff": hours_to_kickoff,
                "raw": fx,
            }
        )
    return out


__all__ = ["build_features"]
