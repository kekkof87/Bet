from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from core.logging import get_logger
from core.config import get_settings

logger = get_logger("providers.odds.stub")


class StubOddsProvider:
    """
    Provider stub veloce:
    - Usa la lista fixtures passata
    - Genera quote pseudo-random coerenti con differenza di probabilità basata su eventuali punteggi
    - Output formato odds_entry: fixture_id, source, ts, market: {home_win, draw, away_win}
    NOTA: NON rappresenta odds reali, serve solo pipeline wiring.
    """

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        settings = get_settings()
        self.source = settings.odds_default_source

    def fetch_odds(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        out: List[Dict[str, Any]] = []
        for fx in fixtures:
            fid = fx.get("fixture_id")
            if fid is None:
                continue
            # base pseudo-probs
            home_score = fx.get("home_score") or 0
            away_score = fx.get("away_score") or 0
            score_diff = 0
            try:
                score_diff = int(home_score) - int(away_score)
            except Exception:
                score_diff = 0

            # bias semplice su probabilità implicite
            base_home = 0.33 + 0.03 * score_diff
            base_away = 0.34 - 0.03 * score_diff
            base_draw = 1 - base_home - base_away
            # clamp
            for _ in range(2):
                if base_draw < 0.05:
                    excess = 0.05 - base_draw
                    base_home -= excess / 2
                    base_away -= excess / 2
                    base_draw = 0.05
                s = base_home + base_draw + base_away
                base_home /= s
                base_draw /= s
                base_away /= s

            # Convertiamo a quote (decimal odds) = 1 / prob con jitter
            def to_odds(p: float) -> float:
                j = random.uniform(-0.02, 0.02)
                val = max(p + j, 0.02)
                return round(1 / val, 3)

            odds_entry = {
                "fixture_id": fid,
                "source": self.source,
                "fetched_at": now,
                "market": {
                    "home_win": to_odds(base_home),
                    "draw": to_odds(base_draw),
                    "away_win": to_odds(base_away),
                },
            }
            out.append(odds_entry)
        logger.info("stub_odds_generated", extra={"count": len(out)})
        return out
