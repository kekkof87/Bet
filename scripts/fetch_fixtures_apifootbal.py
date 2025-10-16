#!/usr/bin/env python3
import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

# .env override
try:
    from dotenv import load_dotenv, find_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
except Exception:
    pass

import requests

def clean_key(k: str) -> str:
    return k.strip().strip("'\"").replace("\ufeff", "")

# Provider auto
PROVIDER = None
API_SPORTS_KEY = clean_key(os.environ.get("APIFOOTBALL_API_KEY", ""))
RAPIDAPI_KEY = clean_key(os.environ.get("RAPIDAPI_KEY", ""))

if API_SPORTS_KEY:
    PROVIDER = "apisports"
elif RAPIDAPI_KEY:
    PROVIDER = "rapidapi"

def provider_config() -> Dict[str, Any]:
    if PROVIDER == "apisports":
        base = "https://v3.football.api-sports.io"
        # doppio header per eventuali bug di case-sensitivity lungo la catena
        headers = {
            "x-apisports-key": API_SPORTS_KEY,
            "X-APISports-Key": API_SPORTS_KEY,
            "Accept": "application/json",
            "User-Agent": "betting-dashboard/1.0",
            "Connection": "close",
        }
        return {"base": base, "headers": headers, "label": "API-Sports direct"}
    elif PROVIDER == "rapidapi":
        base = "https://api-football-v1.p.rapidapi.com/v3"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
            "Accept": "application/json",
            "User-Agent": "betting-dashboard/1.0",
            "Connection": "close",
        }
        return {"base": base, "headers": headers, "label": "RapidAPI"}
    return {}

def new_session(headers: Dict[str, str]) -> requests.Session:
    s = requests.Session()
    # ignora variabili d’ambiente di proxy (trust_env=False)
    s.trust_env = False
    s.headers.update(headers)
    s.max_redirects = 5
    return s

def http_get(session: requests.Session, url: str, timeout: int = 25) -> Tuple[Dict[str, Any], Dict[str, str], str]:
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    final_url = str(resp.url)
    text = resp.text
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": text}
    if not resp.ok:
        sys.stderr.write(f"[fixtures] HTTP {resp.status_code} url={final_url} body={text[:300]}\n")
        resp.raise_for_status()
    hdrs = {k.lower(): v for k, v in resp.headers.items()}
    return payload, hdrs, final_url

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
            items.append({
                "fixture_id": fid,
                "home": home,
                "away": away,
                "league": league,
                "status": status,
                "kickoff": kickoff,
            })
        except Exception:
            continue
    return items

def iter_dates(days: int, start_utc: Optional[date] = None) -> List[date]:
    if start_utc is None:
        start_utc = datetime.now(timezone.utc).date()
    return [start_utc + timedelta(days=i) for i in range(days)]

def fetch_by_date(session: requests.Session, days: int, tz: str, base: str, league_ids: Optional[List[int]] = None, sleep_s: float = 0.2) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    tz_q = urllib.parse.quote(tz)
    for d in iter_dates(days):
        if league_ids:
            lids = league_ids
        else:
            lids = [None]
        for lid in lids:
            url = f"{base}/fixtures?date={d.isoformat()}&timezone={tz_q}" + (f"&league={lid}" if lid else "")
            payload, hdrs, final = http_get(session, url)
            errs = payload.get("errors") or {}
            if errs:
                sys.stderr.write(f"[fixtures] errors on date={d}{' league='+str(lid) if lid else ''}: {errs}\n")
            params = payload.get("parameters")
            if params is not None:
                sys.stderr.write(f"[fixtures] parameters={params} results={payload.get('results')}, final_url={final}\n")
            rl = hdrs.get("x-ratelimit-requests-remaining") or hdrs.get("x-ratelimit-remaining")
            if rl is not None:
                sys.stderr.write(f"[fixtures] rate-limit remaining={rl}\n")
            items = normalize_items(payload.get("response", []))
            for it in items:
                if it["fixture_id"] not in seen_ids:
                    seen_ids.add(it["fixture_id"])
                    collected.append(it)
            time.sleep(sleep_s)
    return collected

def fetch_by_range(session: requests.Session, days: int, base: str) -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    date_from = today
    date_to = today + timedelta(days=days)
    url = f"{base}/fixtures?from={date_from.isoformat()}&to={date_to.isoformat()}"
    payload, hdrs, final = http_get(session, url)
    errs = payload.get("errors") or {}
    if errs:
        sys.stderr.write(f"[fixtures] range errors: {errs}\n")
    params = payload.get("parameters")
    if params is not None:
        sys.stderr.write(f"[fixtures] range parameters={params} results={payload.get('results')}, final_url={final}\n")
    rl = hdrs.get("x-ratelimit-requests-remaining") or hdrs.get("x-ratelimit-remaining")
    if rl is not None:
        sys.stderr.write(f"[fixtures] rate-limit remaining={rl}\n")
    return normalize_items(payload.get("response", []))

def main():
    cfg = provider_config()
    if not cfg:
        sys.stderr.write("[fixtures] Nessuna chiave trovata. Metti APIFOOTBALL_API_KEY (API-Sports) oppure RAPIDAPI_KEY (RapidAPI) in .env\n")
        sys.exit(1)

    provider_label = cfg["label"]
    base = cfg["base"]
    headers = cfg["headers"]

    masked = "****"
    if PROVIDER == "apisports":
        masked = (API_SPORTS_KEY[:4] + "…") if API_SPORTS_KEY else "(vuota)"
    elif PROVIDER == "rapidapi":
        masked = (RAPIDAPI_KEY[:4] + "…") if RAPIDAPI_KEY else "(vuota)"
    print(f"[fixtures] Provider={provider_label}, base={base}, key={masked}")

    # Session senza proxy
    session = new_session(headers)

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    fetch_days = int(os.environ.get("FETCH_DAYS", "3"))
    timezone_str = os.environ.get("TIMEZONE", "Europe/Rome")
    league_ids_env = os.environ.get("LEAGUE_IDS", "").strip()
    league_ids: Optional[List[int]] = None
    if league_ids_env:
        try:
            league_ids = [int(x) for x in league_ids_env.replace(" ", "").split(",") if x]
        except Exception:
            sys.stderr.write(f"[fixtures] LEAGUE_IDS non valida: {league_ids_env}\n")

    # 1) per-data
    try:
        items = fetch_by_date(session, fetch_days, timezone_str, base, league_ids=league_ids)
    except Exception as e:
        sys.stderr.write(f"[fixtures] errore fetch_by_date: {e}\n")
        items = []

    # 2) fallback by-range
    if not items:
        sys.stderr.write("[fixtures] Nessun evento per-data, provo fallback by-range (UTC).\n")
        try:
            items = fetch_by_range(session, fetch_days, base)
        except Exception as e:
            sys.stderr.write(f"[fixtures] errore fetch_by_range: {e}\n")
            items = []

    save_json(data_dir / "last_delta.json", {"added": items})
    save_json(data_dir / "fixtures.json", {"generated_from": provider_label, "count": len(items), "items": items})
    print(f"[fixtures] Scritti {len(items)} fixtures in data/fixtures.json e data/last_delta.json (days={fetch_days}, tz={timezone_str}, leagues={league_ids or 'ALL'})")

if __name__ == "__main__":
    main()
