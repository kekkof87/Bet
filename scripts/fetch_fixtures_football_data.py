#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

# Carica .env (override=True)
try:
    from dotenv import load_dotenv, find_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
except Exception:
    pass

import requests

BASE = "https://api.football-data.org/v4"

STATUS_MAP = {
    "SCHEDULED": "NS",
    "TIMED": "NS",
    "LIVE": "LIVE",
    "IN_PLAY": "LIVE",
    "PAUSED": "LIVE",
    "FINISHED": "FT",
    "POSTPONED": "PST",
    "SUSPENDED": "SUSP",
    "CANCELED": "CANC",
}

def clean_key(k: str) -> str:
    return k.strip().strip("'\"").replace("\ufeff", "")

def new_session(token: str) -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # ignora proxy di sistema
    s.headers.update({
        "X-Auth-Token": token,
        "Accept": "application/json",
        "User-Agent": "betting-dashboard/1.0",
        "Connection": "close",
    })
    return s

def save_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def normalize_items(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for m in matches:
        try:
            fid = m.get("id")
            comp = (m.get("competition") or {}).get("name")
            home = (m.get("homeTeam") or {}).get("name")
            away = (m.get("awayTeam") or {}).get("name")
            kickoff = m.get("utcDate")
            status_raw = m.get("status")
            status = STATUS_MAP.get(status_raw, status_raw or "")
            if not fid or not home or not away:
                continue
            items.append({
                "fixture_id": fid,
                "home": home,
                "away": away,
                "league": comp,
                "status": status,
                "kickoff": kickoff,  # ISO UTC
            })
        except Exception:
            continue
    return items

def fetch_matches(session: requests.Session, date_from: date, date_to: date, competitions: Optional[str]) -> Tuple[List[Dict[str, Any]], Dict[str, str], str]:
    params = {
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
    }
    if competitions:
        params["competitions"] = competitions  # es: "PL,SA,PD,BL1,FL1"
    url = f"{BASE}/matches?{urllib.parse.urlencode(params)}"
    resp = session.get(url, timeout=25, allow_redirects=True)
    final_url = str(resp.url)
    text = resp.text
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": text}
    if not resp.ok:
        sys.stderr.write(f"[fdo] HTTP {resp.status_code} url={final_url} body={text[:300]}\n")
        resp.raise_for_status()
    hdrs = {k.lower(): v for k, v in resp.headers.items()}
    matches = payload.get("matches", [])
    return matches, hdrs, final_url

def main():
    token = clean_key(os.environ.get("FOOTBALL_DATA_API_KEY", ""))
    if not token:
        sys.stderr.write("[fdo] FOOTBALL_DATA_API_KEY non impostata (.env o variabile d'ambiente).\n")
        sys.exit(1)

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    fetch_days = int(os.environ.get("FETCH_DAYS", "7"))  # default 7 giorni
    competitions = os.environ.get("LEAGUE_CODES", "").strip()  # es: "PL,SA,PD" (opzionale)

    today = datetime.now(timezone.utc).date()
    date_from = today
    date_to = today + timedelta(days=fetch_days)

    session = new_session(token)
    print(f"[fdo] dateFrom={date_from} dateTo={date_to} comps={competitions or 'ALL'}")

    try:
        matches, hdrs, final_url = fetch_matches(session, date_from, date_to, competitions or None)
    except Exception as e:
        sys.stderr.write(f"[fdo] errore fetch: {e}\n")
        sys.exit(2)

    items = normalize_items(matches)

    # Log rate-limit se presente
    for k, v in hdrs.items():
        if k.startswith("x-requests-available") or k.startswith("x-requests-used"):
            sys.stderr.write(f"[fdo] {k}: {v}\n")

    save_json(data_dir / "last_delta.json", {"added": items})
    save_json(data_dir / "fixtures.json", {"generated_from": "football-data.org", "count": len(items), "items": items})
    print(f"[fdo] Scritti {len(items)} fixtures in data/fixtures.json e data/last_delta.json (days={fetch_days}, comps={competitions or 'ALL'})")

if __name__ == "__main__":
    main()
