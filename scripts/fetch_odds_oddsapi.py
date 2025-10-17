#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p:
        load_dotenv(p, override=True)
except Exception:
    pass

import requests

API_BASE = "https://api.the-odds-api.com/v4"
REGION = os.environ.get("ODDS_REGION", "eu")  # eu/uk/us/au
MARKETS = "h2h"  # esiti 1X2
ODDS_FORMAT = "decimal"

# Mapping indicativo Competition Code (FDO) -> The Odds API sport keys
FDO_TO_ODDSAPI = {
    "PL": "soccer_epl",
    "PD": "soccer_spain_la_liga",
    "SA": "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
    # estendibile
}

def normalize_name(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch.isspace()).strip()

def load_fixtures(data_dir: Path) -> List[Dict[str, Any]]:
    fx_path = data_dir / "fixtures.json"
    if not fx_path.exists():
        return []
    obj = json.loads(fx_path.read_text(encoding="utf-8"))
    return obj.get("items", obj) if isinstance(obj, dict) else obj

def fetch_sport_odds(session: requests.Session, api_key: str, sport_key: str) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": REGION, "markets": MARKETS, "oddsFormat": ODDS_FORMAT}
    r = session.get(url, params=params, timeout=30)
    if not r.ok:
        sys.stderr.write(f"[odds] HTTP {r.status_code} {r.url} {r.text[:300]}\n")
        r.raise_for_status()
    return r.json()

def choose_best_h2h(bookmakers: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Estrae best home/draw/away e bookmaker vincente
    best = {"home": 0.0, "draw": 0.0, "away": 0.0, "book": None}
    best_book = None
    for bk in bookmakers:
        key = bk.get("key") or bk.get("title")
        markets = bk.get("markets") or []
        for m in markets:
            if m.get("key") != "h2h":
                continue
            for outc in m.get("outcomes", []):
                name = str(outc.get("name") or "").lower()
                price = float(outc.get("price") or 0.0)
                if name in ("home", "home team"):
                    if price > best["home"]:
                        best["home"] = price
                        best_book = key
                elif name in ("draw", "tie"):
                    if price > best["draw"]:
                        best["draw"] = price
                        best_book = key
                elif name in ("away", "away team"):
                    if price > best["away"]:
                        best["away"] = price
                        best_book = key
    if best_book:
        best["book"] = best_book
    return best

def main():
    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        sys.stderr.write("[odds] ODDS_API_KEY non impostata (.env)\n")
        sys.exit(1)

    fixtures = load_fixtures(data_dir)
    if not fixtures:
        sys.stderr.write("[odds] Nessun fixtures.json; esegui prima fetch fixtures FDO.\n")
        sys.exit(2)

    # Pre-indicizzazione fixtures per matching per (home, away, kickoff)
    fx_index: List[Tuple[str, str, datetime, Dict[str, Any]]] = []
    for fx in fixtures:
        try:
            ko = datetime.fromisoformat(str(fx.get("kickoff")).replace("Z", "+00:00"))
        except Exception:
            continue
        fx_index.append((normalize_name(fx.get("home")), normalize_name(fx.get("away")), ko, fx))

    session = requests.Session()
    session.trust_env = False
    out_items: List[Dict[str, Any]] = []

    # Determina sport_keys da interrogare: per MVP usiamo lista fissa top5
    sport_keys = list(set(FDO_TO_ODDSAPI.values()))

    for sport in sport_keys:
        try:
            events = fetch_sport_odds(session, api_key, sport)
        except Exception as e:
            sys.stderr.write(f"[odds] errore fetch sport {sport}: {e}\n")
            continue

        for ev in events:
            # Struttura tipica: {id, sport_key, commence_time, home_team, away_team, bookmakers:[{key, markets:[{key:'h2h', outcomes:[{name, price}]}]}]}
            home = normalize_name(ev.get("home_team"))
            away = normalize_name(ev.get("away_team"))
            try:
                ct = datetime.fromisoformat(str(ev.get("commence_time")).replace("Z", "+00:00"))
            except Exception:
                ct = None
            if not home or not away or not ct:
                continue
            # Matching: stesso home/away normalizzato e kickoff entro ±3 ore
            for H, A, KO, FX in fx_index:
                if H == home and A == away and abs((KO - ct).total_seconds()) <= 3 * 3600:
                    best = choose_best_h2h(ev.get("bookmakers", []))
                    out_items.append({
                        "fixture_id": FX.get("fixture_id"),
                        "home": FX.get("home"),
                        "away": FX.get("away"),
                        "league": FX.get("league"),
                        "kickoff": FX.get("kickoff"),
                        "market": "1X2",
                        "best": best,
                        "raw_event_id": ev.get("id"),
                        "sport_key": sport,
                    })
                    break

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": out_items}
    (data_dir / "odds_latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[odds] Scritti {len(out_items)} eventi con best odds in data/odds_latest.json")

if __name__ == "__main__":
    main()
