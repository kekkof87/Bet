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
import urllib.parse

# Carica .env (override=True) cercandolo dalla cwd in su
try:
    from dotenv import load_dotenv, find_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
except Exception:
    pass

def clean_key(k: str) -> str:
    # rimuove spazi, apici, BOM e caratteri non stampabili
    k = k.strip().strip("'\"").replace("\ufeff", "")
    return k

# Provider auto-detection:
# - API-Sports diretto: usa APIFOOTBALL_API_KEY su v3.football.api-sports.io
# - RapidAPI: usa RAPIDAPI_KEY su api-football-v1.p.rapidapi.com
PROVIDER = None
API_SPORTS_KEY = clean_key(os.environ.get("APIFOOTBALL_API_KEY", ""))
RAPIDAPI_KEY = clean_key(os.environ.get("RAPIDAPI_KEY", ""))

if API_SPORTS_KEY:
    PROVIDER = "apisports"
elif RAPIDAPI_KEY:
    PROVIDER = "rapidapi"

def provider_config() -> Dict[str, Any]:
    if PROVIDER == "apisports":
        return {
            "base": "https://v3.football.api-sports.io",
            "headers": {
                "x-apisports-key": API_SPORTS_KEY,
                "Accept": "application/json",
                "User-Agent": "betting-dashboard/1.0",
            },
            "label": "API-Sports direct",
        }
    elif PROVIDER == "rapidapi":
        return {
            "base": "https://api-football-v1.p.rapidapi.com/v3",
            "headers": {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
                "Accept": "application/json",
                "User-Agent": "betting-dashboard/1.0",
            },
            "label": "RapidAPI",
        }
    else:
        return {}

def build_opener_disable_proxy() -> urllib.request.OpenerDirector:
    # Disabilita qualsiasi proxy di sistema/ENV che potrebbe rimuovere header custom
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

OPENER = build_opener_disable_proxy()

def http_get(url: str, headers: Dict[str, str], timeout: int = 25) -> Tuple[Dict[str, Any], Dict[str, str]]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with OPENER.open(req, timeout=timeout) as resp:
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

def fetch_by_date(days: int, tz: str, headers: Dict[str, str], base: str, league_ids: Optional[List[int]] = None, sleep_s: float = 0.25) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    tz_q = urllib.parse.quote(tz)
    for d in iter_dates(days):
        if league_ids:
            for lid in league_ids:
                url = f"{base}/fixtures?date={d.isoformat()}&timezone={tz_q}&league={lid}"
                payload, hdrs = http_get(url, headers)
                if "errors" in payload and payload["errors"]:
                    print(f"[fixtures] errors on date={d} league={lid}: {payload['errors']}", file=sys.stderr)
                if "parameters" in payload:
                    print(f"[fixtures] parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
                # prova a loggare headers di rate limit per capire se la chiave è stata accettata
                rl = hdrs.get("x-ratelimit-requests-remaining")
                if rl is not None:
                    print(f"[fixtures] rate-limit remaining={rl}", file=sys.stderr)
                items = normalize_items(payload.get("response", []))
                for it in items:
                    if it["fixture_id"] not in seen_ids:
                        seen_ids.add(it["fixture_id"])
                        collected.append(it)
                time.sleep(sleep_s)
        else:
            url = f"{base}/fixtures?date={d.isoformat()}&timezone={tz_q}"
            payload, hdrs = http_get(url, headers)
            if "errors" in payload and payload["errors"]:
                print(f"[fixtures] errors on date={d}: {payload['errors']}", file=sys.stderr)
            if "parameters" in payload:
                print(f"[fixtures] parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
            rl = hdrs.get("x-ratelimit-requests-remaining")
            if rl is not None:
                print(f"[fixtures] rate-limit remaining={rl}", file=sys.stderr)
            items = normalize_items(payload.get("response", []))
            for it in items:
                if it["fixture_id"] not in seen_ids:
                    seen_ids.add(it["fixture_id"])
                    collected.append(it)
            time.sleep(sleep_s)
    return collected

def fetch_by_range(days: int, headers: Dict[str, str], base: str) -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    date_from = today
    date_to = today + timedelta(days=days)
    url = f"{base}/fixtures?from={date_from.isoformat()}&to={date_to.isoformat()}"
    payload, hdrs = http_get(url, headers)
    if "errors" in payload and payload["errors"]:
        print(f"[fixtures] range errors: {payload['errors']}", file=sys.stderr)
    if "parameters" in payload:
        print(f"[fixtures] range parameters={payload['parameters']} results={payload.get('results')}", file=sys.stderr)
    rl = hdrs.get("x-ratelimit-requests-remaining")
    if rl is not None:
        print(f"[fixtures] rate-limit remaining={rl}", file=sys.stderr)
    return normalize_items(payload.get("response", []))

def main():
    cfg = provider_config()
    if not cfg:
        print("[fixtures] Nessuna chiave trovata. Metti APIFOOTBALL_API_KEY (API-Sports) oppure RAPIDAPI_KEY (RapidAPI) nel file .env", file=sys.stderr)
        sys.exit(1)

    provider_label = cfg["label"]
    base = cfg["base"]
    headers = cfg["headers"].copy()

    # Debug minimo (mascherato)
    masked = "****"
    if PROVIDER == "apisports":
        masked = (API_SPORTS_KEY[:4] + "…") if API_SPORTS_KEY else "(vuota)"
    elif PROVIDER == "rapidapi":
        masked = (RAPIDAPI_KEY[:4] + "…") if RAPIDAPI_KEY else "(vuota)"
    print(f"[fixtures] Provider={provider_label}, base={base}, key={masked}")

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    fetch_days = int(os.environ.get("FETCH_DAYS", "3"))
    timezone_str = os.environ.get("TIMEZONE", "Europe/Rome")
    league_ids_env = os.environ.get("LEAGUE_IDS", "").strip()
    league_ids: Optional[List[int]] = None
    if league_ids_env:
        try:
            league_ids = [int(x) for x in league_ids_env.replace(" ", "").split(",") if x]
        except Exception:
            print(f"[fixtures] LEAGUE_IDS non valida: {league_ids_env}", file=sys.stderr)

    # 1) per-data con timezone (e filtri lega opzionali)
    try:
        items = fetch_by_date(fetch_days, timezone_str, headers, base, league_ids=league_ids)
    except Exception as e:
        print(f"[fixtures] errore fetch_by_date: {e}", file=sys.stderr)
        items = []

    # 2) fallback by-range UTC
    if not items:
        print("[fixtures] Nessun evento per-data, provo fallback by-range (UTC).", file=sys.stderr)
        try:
            items = fetch_by_range(fetch_days, headers, base)
        except Exception as e:
            print(f"[fixtures] errore fetch_by_range: {e}", file=sys.stderr)
            items = []

    save_json(data_dir / "last_delta.json", {"added": items})
    save_json(data_dir / "fixtures.json", {"generated_from": provider_label, "count": len(items), "items": items})
    print(f"[fixtures] Scritti {len(items)} fixtures in data/fixtures.json e data/last_delta.json (days={fetch_days}, tz={timezone_str}, leagues={league_ids or 'ALL'})")

if __name__ == "__main__":
    main()
