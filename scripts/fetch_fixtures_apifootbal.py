#!/usr/bin/env python3
import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

# Carica .env (override=True) cercandolo a partire dalla cwd
try:
    from dotenv import load_dotenv, find_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
except Exception:
    pass

API_BASE = "https://v3.football.api-sports.io"

def http_get(url: str, headers: Dict[str, str], timeout: int = 25) -> Tuple[Dict[str, Any], Dict[str, str]]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return payload, hdrs
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        print(f"[fixtures] HTTPError {e.code}: {e.reason} url={url} body={body}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"[fixtures] URLError: {e.reason} url={url}", file=sys.stderr)
        raise

def save_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def normalize_items(resp: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for r in resp:
        try:
            fx = r.get("fixture", {}) or {}
            lg = r.get("league", {}) or {}
            tm = r.get("teams", {}) or {}
            fid = fx.get("id")
            status = (fx.get("status", {}) or {}).get("short", "")
            kickoff = fx.get("date")
            home = (tm.get("home", {}) or {}).get("name")
            away = (tm.get("away", {}) or {}).get("name")
            league = lg.get("name")
            if not fid or not home or not away:
                continue
            items.append(
                {
                    "fixture_id": fid,
                    "home": home,
                    "away": away,
                    "league": league,
                    "status": status,
                    "kickoff": kickoff,
                }
            )
        except Exception:
            continue
    return items

def iter_dates(days: int, start_utc: Optional[date] = None) -> List[date]:
    if start_utc is None:
        start_utc = datetime.now(timezone.utc).date()
    return [start_utc + timedelta(days=i) for i in range(days)]

def fetch_by_date(days: int, tz: str, headers: Dict[str, str], league_ids: Optional[List[int]] = None, sleep_s: float = 0.25) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    for d in iter_dates(days):
        if league_ids:
            for lid in league_ids:
                url = f"{API_BASE}/fixtures?date={d.isoformat()}&timezone={urllib.parse.quote(tz)}&league={lid}"
                payload, hdrs = http_get(url, headers)
                if "errors" in payload and payload["errors"]:
                    print(f"[fixtures] errors on date={d} league={lid}: {payload['errors']}", file=sys.stderr)
                if "parameters" in payload:
                    print(f"[fixtures] parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
                items = normalize_items(payload.get("response", []))
                for it in items:
                    if it["fixture_id"] not in seen_ids:
                        seen_ids.add(it["fixture_id"])
                        collected.append(it)
                time.sleep(sleep_s)
        else:
            url = f"{API_BASE}/fixtures?date={d.isoformat()}&timezone={urllib.parse.quote(tz)}"
            payload, hdrs = http_get(url, headers)
            if "errors" in payload and payload["errors"]:
                print(f"[fixtures] errors on date={d}: {payload['errors']}", file=sys.stderr)
            if "parameters" in payload:
                print(f"[fixtures] parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
            items = normalize_items(payload.get("response", []))
            for it in items:
                if it["fixture_id"] not in seen_ids:
                    seen_ids.add(it["fixture_id"])
                    collected.append(it)
            time.sleep(sleep_s)
    return collected

def fetch_by_range(days: int, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    date_from = today
    date_to = today + timedelta(days=days)
    url = f"{API_BASE}/fixtures?from={date_from.isoformat()}&to={date_to.isoformat()}"
    payload, hdrs = http_get(url, headers)
    if "errors" in payload and payload["errors"]:
        print(f"[fixtures] range errors: {payload['errors']}", file=sys.stderr)
    if "parameters" in payload:
        print(f"[fixtures] range parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
    return normalize_items(payload.get("response", []))

def main():
    api_key = os.environ.get("APIFOOTBALL_API_KEY")
    if not api_key:
        print("[fixtures] APIFOOTBALL_API_KEY non impostata (.env o variabile d'ambiente).", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    fetch_days = int(os.environ.get("FETCH_DAYS", "3"))  # allarga la finestra: default 3 giorni
    timezone_str = os.environ.get("TIMEZONE", "Europe/Rome")  # timezone per taglio di giornata locale
    league_ids_env = os.environ.get("LEAGUE_IDS", "").strip()
    league_ids: Optional[List[int]] = None
    if league_ids_env:
        try:
            league_ids = [int(x) for x in league_ids_env.replace(" ", "").split(",") if x]
        except Exception:
            print(f"[fixtures] LEAGUE_IDS non valida: {league_ids_env}", file=sys.stderr)

    headers = {
        "x-apisports-key": api_key,
        "Accept": "application/json",
        "User-Agent": "betting-dashboard/1.0",
    }

    # 1) Prova modalità per data (giorno per giorno, con timezone e opzionale league filter)
    try:
        items = fetch_by_date(fetch_days, timezone_str, headers, league_ids=league_ids)
    except Exception as e:
        print(f"[fixtures] errore fetch_by_date: {e}", file=sys.stderr)
        items = []

    # 2) Se 0 risultati, fallback a range UTC
    if not items:
        print("[fixtures] Nessun evento trovato in modalita' per-data, provo il fallback by-range (UTC).", file=sys.stderr)
        try:
            items = fetch_by_range(fetch_days, headers)
        except Exception as e:
            print(f"[fixtures] errore fetch_by_range: {e}", file=sys.stderr)
            items = []

    # Scrivi output
    save_json(data_dir / "last_delta.json", {"added": items})
    save_json(data_dir / "fixtures.json", {"generated_from": "apifootball", "count": len(items), "items": items})
    print(f"[fixtures] Scritti {len(items)} fixtures in data/fixtures.json e data/last_delta.json (days={fetch_days}, tz={timezone_str}, leagues={league_ids or 'ALL'})")

if __name__ == "__main__":
    main()
