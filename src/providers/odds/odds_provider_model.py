from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List

from providers.football_data.fixtures_provider import FootballDataFixturesProvider


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _probs_to_odds(p: Dict[str, float]) -> Dict[str, float]:
    return {k: round(1.0 / max(1e-9, v), 3) for k, v in p.items()}


def _compute_probs(home_rating: float, away_rating: float) -> Dict[str, float]:
    # Modello semplice:
    # - diff = rHome - rAway
    # - vantaggio casa 0.25
    # - base draw 0.26 che decresce con mismatch
    diff = home_rating - away_rating
    home_adv = 0.25
    k = 0.9
    base_draw = 0.26
    alpha = 0.08

    p_home_no_draw = _sigmoid(k * (diff + home_adv))
    p_away_no_draw = 1.0 - p_home_no_draw
    p_draw = _clamp(base_draw - alpha * abs(diff), 0.18, 0.30)
    scale = 1.0 - p_draw
    p_home = p_home_no_draw * scale
    p_away = p_away_no_draw * scale
    s = (p_home + p_draw + p_away) or 1.0
    return {
        "home_win": p_home / s,
        "draw": p_draw / s,
        "away_win": p_away / s,
    }


class ModelOddsProvider:
    """
    Genera fair odds 1X2 dal modello standings-based (gratuito).
    Restituisce la stessa struttura della stub per compatibilità:
      { "fixture_id", "source", "fetched_at", "market": {home_win, draw, away_win} }
    """

    def __init__(self) -> None:
        self.fd = FootballDataFixturesProvider()

    def fetch_odds(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Pre-carica ratings per tutte le competizioni coinvolte
        comp_codes = {str(f.get("league_id") or "").strip() for f in fixtures if f.get("league_id")}
        ratings_by_comp: Dict[str, Dict[str, float]] = {}
        for code in comp_codes:
            try:
                ratings_by_comp[code] = self.fd.get_standings_map(code)
            except Exception:
                ratings_by_comp[code] = {}

        now = datetime.now(timezone.utc).isoformat()
        out: List[Dict[str, Any]] = []
        for f in fixtures:
            fid = f.get("fixture_id")
            code = str(f.get("league_id") or "").strip()
            home = str(f.get("home_team") or "")
            away = str(f.get("away_team") or "")
            rmap = ratings_by_comp.get(code, {})
            r_home = float(rmap.get(home, 0.0))
            r_away = float(rmap.get(away, 0.0))
            probs = _compute_probs(r_home, r_away)
            odds = _probs_to_odds(probs)
            out.append(
                {
                    "fixture_id": fid,
                    "source": "model",
                    "fetched_at": now,
                    "market": {
                        "home_win": odds["home_win"],
                        "draw": odds["draw"],
                        "away_win": odds["away_win"],
                    },
                }
            )
        return out
