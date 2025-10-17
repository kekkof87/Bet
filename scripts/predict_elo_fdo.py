#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Tuple, List

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_jsonl(path: Path):
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            out.append(json.loads(line))
    return out

def k_factor(goals_home: int, goals_away: int) -> float:
    margin = abs(goals_home - goals_away)
    base = 20.0
    if margin >= 2: base += 5.0
    return base

def expected_score(diff: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

def three_way_probs(diff: float, base_draw: float = 0.25) -> Tuple[float, float, float]:
    p_home_2way = expected_score(diff)
    p_away_2way = 1.0 - p_home_2way
    closeness = max(0.0, 1.0 - abs(diff) / 400.0)
    p_draw = max(0.05, min(0.35, base_draw * (0.5 + 0.5 * closeness)))
    rem = 1.0 - p_draw
    p_home = p_home_2way * rem
    p_away = p_away_2way * rem
    s = p_home + p_draw + p_away
    return p_home / s, p_draw / s, p_away / s

def normalize_name(name: str) -> str:
    return (name or "").strip().lower()

def main():
    data_dir = Path(os.environ.get("DATA_DIR","data"))
    hist_file = data_dir / "history" / "results.jsonl"
    fixtures_file = data_dir / "fixtures.json"
    sources_dir = data_dir / "predictions" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    latest_out = data_dir / "latest_predictions.json"

    if not hist_file.exists():
        print("[elo] History non trovato. Esegui prima: Fetch results (FDO).", file=sys.stderr)
        sys.exit(1)
    if not fixtures_file.exists():
        print("[elo] Fixtures non trovati. Esegui prima il fetch fixtures.", file=sys.stderr)
        sys.exit(1)

    history = load_jsonl(hist_file)
    fixtures = load_json(fixtures_file).get("items", [])

    R: Dict[str, float] = {}
    HA = 70.0  # home advantage

    def get_R(team: str) -> float:
        key = normalize_name(team)
        return R.get(key, 1500.0)

    def set_R(team: str, val: float):
        R[normalize_name(team)] = val

    for m in history:
        home = m.get("home"); away = m.get("away")
        if not home or not away: continue
        ft = m.get("fullTime") or {}
        gh = int(ft.get("home", 0) or 0)
        ga = int(ft.get("away", 0) or 0)

        Rh = get_R(home)
        Ra = get_R(away)
        Eh = expected_score((Rh + HA) - Ra)
        Ea = 1.0 - Eh
        if gh > ga:
            Sh, Sa = 1.0, 0.0
        elif gh < ga:
            Sh, Sa = 0.0, 1.0
        else:
            Sh, Sa = 0.5, 0.5
        K = k_factor(gh, ga)
        Rh_new = Rh + K * (Sh - Eh)
        Ra_new = Ra + K * (Sa - Ea)
        set_R(home, Rh_new)
        set_R(away, Ra_new)

    items = []
    for fx in fixtures:
        fid = fx.get("fixture_id")
        home = fx.get("home")
        away = fx.get("away")
        league = fx.get("league")
        kickoff = fx.get("kickoff")
        if not home or not away or not fid:
            continue
        Rh = get_R(home)
        Ra = get_R(away)
        diff = (Rh + HA) - Ra
        ph, pd, pa = three_way_probs(diff)
        items.append({
            "fixture_id": fid,
            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff,
            "status": fx.get("status"),
            "model": "elo_fdo",
            "probabilities": {"home": ph, "draw": pd, "away": pa}
        })

    ts = datetime.now(timezone.utc).isoformat()
    src_path = sources_dir / f"elo_fdo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with src_path.open("w", encoding="utf-8") as f:
        json.dump({"generated_at": ts, "source": "elo_fdo", "items": items}, f, ensure_ascii=False, indent=2)
    with latest_out.open("w", encoding="utf-8") as f:
        json.dump({"generated_at": ts, "source": "elo_fdo", "items": items}, f, ensure_ascii=False, indent=2)

    print(f"[elo] Predizioni scritte in {src_path.name} e latest_predictions.json (n={len(items)})")

if __name__ == "__main__":
    main()
