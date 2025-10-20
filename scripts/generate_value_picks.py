#!/usr/bin/env python3
import os
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p:
        load_dotenv(p, override=True)
except Exception:
    pass

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def normalize_fixtures() -> List[Dict[str, Any]]:
    fx = DATA_DIR / "fixtures.json"
    if not fx.exists():
        sys.stderr.write("[vp] fixtures.json non trovato. Esegui 'Fetch fixtures (Football-Data.org)'.\n")
        return []
    obj = load_json(fx)
    return obj.get("items", obj) if isinstance(obj, dict) else obj

def load_predictions_idx() -> Dict[str, Dict[str, Any]]:
    p = DATA_DIR / "latest_predictions.json"
    if not p.exists():
        sys.stderr.write("[vp] latest_predictions.json non trovato. Esegui 'Predictions: Elo (FDO)'.\n")
        return {}
    obj = load_json(p)
    items = obj.get("items", obj.get("predictions", obj)) if isinstance(obj, dict) else obj
    out: Dict[str, Dict[str, Any]] = {}
    for it in items if isinstance(items, list) else []:
        fid = str(it.get("fixture_id") or "")
        if fid:
            out[fid] = it
    return out

def load_odds_idx() -> Dict[str, Dict[str, Any]]:
    p = DATA_DIR / "odds_latest.json"
    if not p.exists():
        sys.stderr.write("[vp] odds_latest.json non trovato. Esegui 'Fetch odds (The Odds API)'.\n")
        return {}
    obj = load_json(p)
    items = obj.get("items", obj) if isinstance(obj, dict) else obj
    out: Dict[str, Dict[str, Any]] = {}
    for it in items if isinstance(items, list) else []:
        fid = str(it.get("fixture_id") or it.get("fixture_key") or "")
        if fid:
            out[fid] = it
    return out

def main():
    fixtures = normalize_fixtures()
    preds = load_predictions_idx()
    odds = load_odds_idx()

    if not fixtures or not preds or not odds:
        sys.stderr.write("[vp] Mancano dati: fixtures/predictions/odds. Interrompo.\n")
        sys.exit(1)

    out_items: List[Dict[str, Any]] = []
    for fx in fixtures:
        fid = str(fx.get("fixture_id") or "")
        if not fid:
            continue
        pred = preds.get(fid)
        odd = odds.get(fid)
        if not pred or not odd:
            continue

        probs = pred.get("probabilities") or {}
        ph = float(probs.get("home") or 0.0)
        pd = float(probs.get("draw") or 0.0)
        pa = float(probs.get("away") or 0.0)

        best = odd.get("best", {})  # {"home","draw","away","book"}
        oh = float(best.get("home") or 0.0)
        od = float(best.get("draw") or 0.0)
        oa = float(best.get("away") or 0.0)

        picks: List[Tuple[str, float, float]] = [
            ("home", ph, oh),
            ("draw", pd, od),
            ("away", pa, oa),
        ]
        for sel, p, o in picks:
            if p <= 0.0 or o <= 1.0:
                continue
            fair = 1.0 / p
            edge = (o - fair) / fair
            out_items.append({
                "fixture_id": fid,
                "home": fx.get("home"),
                "away": fx.get("away"),
                "league": fx.get("league"),
                "kickoff": fx.get("kickoff"),
                "status": fx.get("status"),
                "pick": sel,
                "prob": p,
                "fair_odds": fair,
                "best_odds": o,
                "edge": edge,
                "book": best.get("book"),
                "model": pred.get("model", "model"),
            })

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": out_items}
    (DATA_DIR / "value_picks.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[vp] Scritti {len(out_items)} value picks in {DATA_DIR/'value_picks.json'}")

if __name__ == "__main__":
    main()
