from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("predictions.features")


def _parse_iso(dt: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:
        return None


def load_odds_map() -> Dict[int, Dict[str, Any]]:
    """
    Carica odds_latest.json se abilitato l'enrichment con odds.
    Mapping: fixture_id -> {odds_original, odds_implied, odds_margin}
    """
    settings = get_settings()
    if not settings.enable_predictions_use_odds:
        return {}
    base = Path(settings.bet_data_dir or "data")
    fpath = base / settings.odds_dir / "odds_latest.json"
    if not fpath.exists():
        logger.debug("Odds file non trovato: %s", fpath)
        return {}
    try:
        raw = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura odds file: %s", exc)
        return {}

    entries = raw.get("entries") or []
    mapping: Dict[int, Dict[str, Any]] = {}
    for entry in entries:
        fid = entry.get("fixture_id")
        market = entry.get("market")
        if fid is None or not isinstance(market, dict):
            continue
        try:
            home_odds = float(market.get("home_win"))
            draw_odds = float(market.get("draw"))
            away_odds = float(market.get("away_win"))
            if home_odds <= 0 or draw_odds <= 0 or away_odds <= 0:
                continue
            imp_home = 1 / home_odds
            imp_draw = 1 / draw_odds
            imp_away = 1 / away_odds
            total_raw = imp_home + imp_draw + imp_away
            margin = total_raw - 1.0
            norm_home = imp_home / total_raw
            norm_draw = imp_draw / total_raw
            norm_away = imp_away / total_raw
            mapping[int(fid)] = {
                "odds_original": {
                    "home_win": home_odds,
                    "draw": draw_odds,
                    "away_win": away_odds,
                },
                "odds_implied": {
                    "home_win": round(norm_home, 6),
                    "draw": round(norm_draw, 6),
                    "away_win": round(norm_away, 6),
                },
                "odds_margin": round(margin, 6),
            }
        except Exception:
            continue
    logger.debug("Caricate odds per %d fixtures.", len(mapping))
    return mapping


def build_features(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    odds_map = load_odds_map()
    out: List[Dict[str, Any]] = []

    status_map = {"NS": 0, "1H": 1, "HT": 2, "2H": 3, "ET": 4, "AET": 5, "P": 6, "FT": 7}
    live_status = {"1H", "2H", "HT", "ET", "AET", "P"}

    for fx in fixtures:
        fid = fx.get("fixture_id")
        date_raw = fx.get("date_utc")
        dt = _parse_iso(date_raw) if isinstance(date_raw, str) else None

        hours_to_kickoff: Optional[float] = None
        if dt:
            diff_h = (dt - now).total_seconds() / 3600.0
            hours_to_kickoff = round(diff_h, 3)

        hs = fx.get("home_score")
        as_ = fx.get("away_score")
        score_diff = 0
        try:
            if hs is not None and as_ is not None:
                score_diff = int(hs) - int(as_)
        except Exception:
            score_diff = 0

        status = fx.get("status") or "UNK"
        status_code = status_map.get(status, -1)
        is_live = status in live_status

        feat: Dict[str, Any] = {
            "fixture_id": fid,
            "is_live": is_live,
            "score_diff": score_diff,
            "hours_to_kickoff": hours_to_kickoff,
            "status_code": status_code,
        }

        if isinstance(fid, int) and fid in odds_map:
            feat.update(odds_map[fid])

        out.append(feat)
    return out


__all__ = ["build_features", "load_odds_map"]
