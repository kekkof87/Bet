import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from core.config import _reset_settings_cache_for_tests, get_settings
from analytics.roi import build_or_update_roi

def _simulate_finished(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, f in enumerate(fixtures):
        ff = dict(f)
        # Trasforma metà in FT con risultati variabili
        if i % 2 == 0:
            ff["status"] = "FT"
            ff["home_score"] = (i % 3) + 1
            ff["away_score"] = (i % 2)
        out.append(ff)
    return out

def main():
    _reset_settings_cache_for_tests()
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    # Qui NON abbiamo persistenza fixtures normalizzate, quindi inserisci manualmente
    # un set di fixture create 2 minuti fa.
    demo_fixtures = []
    now = datetime.now(timezone.utc)
    for idx in range(6):
        demo_fixtures.append({
            "fixture_id": 7000 + idx,
            "status": "NS",
            "home_score": 0,
            "away_score": 0,
            "league_id": 999,
            "created_ts": now.isoformat()
        })
    finished = _simulate_finished(demo_fixtures)
    build_or_update_roi(finished)

if __name__ == "__main__":
    main()
