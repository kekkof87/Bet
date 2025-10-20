#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p:
        load_dotenv(p, override=True)
except Exception:
    pass

import requests

# Fuzzy optional
try:
    from rapidfuzz import fuzz
    HAS_FUZZ = True
except Exception:
    HAS_FUZZ = False

API_BASE = "https://api.the-odds-api.com/v4"
REGIONS = os.environ.get("ODDS_REGIONS", "eu,uk")  # uno o più, separati da virgola
MARKETS = "h2h"  # esiti 1X2
ODDS_FORMAT = "decimal"
MATCH_WINDOW_SECONDS = int(os.environ.get("ODDS_MATCH_WINDOW_SECONDS", str(3 * 3600)))  # ±3 ore

# Mapping Competition Code (FDO) -> The Odds API sport keys
FDO_TO_ODDSAPI = {
    "PL": "soccer_epl",
    "PD": "soccer_spain_la_liga",
    "SA": "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
    "CL": "soccer_uefa_champs_league",
    "EL": "soccer_uefa_europa_league"
}

def normalize_name(s: str) -> str:
    base = "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch.isspace()).strip()
    return " ".join(base.split())

def load_aliases(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def alias_name(s: str, aliases: Dict[str, List[str]]) -> List[str]:
    # Restituisce lista di possibili varianti per matching
    norm = normalize_name(s)
    out = [norm]
    for k, vals in aliases.items():
        key = normalize_name(k)
        if norm == key:
            out.extend([normalize_name(v) for v in vals])
    return list(dict.fromkeys(out))

def load_fixtures(data_dir: Path) -> List[Dict[str, Any]]:
    fx_path = data_dir / "fixtures.json"
    if not fx_path.exists():
        return []
    obj = json.loads(fx_path.read_text(encoding="utf-8"))
    return obj.get("items", obj) if isinstance(obj, dict) else obj

def fetch_sport_odds(session: requests.Session, api_key: str, sport_key: str, regions: str) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": regions, "markets": MARKETS, "oddsFormat": ODDS_FORMAT}
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

    aliases = load_aliases(data_dir / "aliases" / "teams.json")

    # Pre-indicizzazione fixtures per matching per (home/away alias, kickoff)
    fx_index: List[Tuple[List[str], List[str], datetime, Dict[str, Any]]] = []
    for fx in fixtures:
        try:
            ko = datetime.fromisoformat(str(fx.get("kickoff")).replace("Z", "+00:00"))
        except Exception:
            continue
        homes = alias_name(fx.get("home", ""), aliases)
        aways = alias_name(fx.get("away", ""), aliases)
        fx_index.append((homes, aways, ko, fx))

    session = requests.Session()
    session.trust_env = False
    out_items: List[Dict[str, Any]] = []

    sport_keys = list(set(FDO_TO_ODDSAPI.values()))
    found_count = 0

    for sport in sport_keys:
        try:
            events = fetch_sport_odds(session, api_key, sport, REGIONS)
        except Exception as e:
            sys.stderr.write(f"[odds] errore fetch sport {sport}: {e}\n")
            continue

        for ev in events:
            # Struttura tipica: {id, sport_key, commence_time, home_team, away_team, bookmakers:[...]}
            home_ev = normalize_name(ev.get("home_team"))
            away_ev = normalize_name(ev.get("away_team"))
            try:
                ct = datetime.fromisoformat(str(ev.get("commence_time")).replace("Z", "+00:00"))
            except Exception:
                ct = None
            if not home_ev or not away_ev or not ct:
                continue

            matched_fx: Optional[Dict[str, Any]] = None

            for homes, aways, KO, FX in fx_index:
                time_ok = abs((KO - ct).total_seconds()) <= MATCH_WINDOW_SECONDS
                if not time_ok:
                    continue

                # Match diretto sugli alias generati
                if home_ev in homes and away_ev in aways:
                    matched_fx = FX
                    break

                # Fuzzy fallback (solo se libreria disponibile)
                if HAS_FUZZ:
                    # score su tutte le varianti alias
                    best_h = max((fuzz.ratio(home_ev, h) for h in homes), default=0)
                    best_a = max((fuzz.ratio(away_ev, a) for a in aways), default=0)
                    if best_h >= 92 and best_a >= 92:
                        matched_fx = FX
                        break

            if not matched_fx:
                continue

            best = choose_best_h2h(ev.get("bookmakers", []))
            if best["home"] <= 1.0 and best["draw"] <= 1.0 and best["away"] <= 1.0:
                continue

            out_items.append({
                "fixture_id": matched_fx.get("fixture_id"),
                "home": matched_fx.get("home"),
                "away": matched_fx.get("away"),
                "league": matched_fx.get("league"),
                "kickoff": matched_fx.get("kickoff"),
                "market": "1X2",
                "best": best,
                "raw_event_id": ev.get("id"),
                "sport_key": sport,
                "regions": REGIONS
            })
            found_count += 1

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": out_items}
    (data_dir / "odds_latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[odds] Scritti {found_count} eventi con best odds in data/odds_latest.json (regions={REGIONS}, fuzzy={'on' if HAS_FUZZ else 'off'})")

if __name__ == "__main__":
    main()
