#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
import time

try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p:
        load_dotenv(p, override=True)
except Exception:
    pass

import requests

BASE = "https://api.football-data.org/v4"

def clean(s: str) -> str:
    return s.strip().strip("'\"").replace("\ufeff","")

def new_session(token: str) -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "X-Auth-Token": token,
        "Accept": "application/json",
        "User-Agent": "betting-dashboard/1.0",
        "Connection": "close",
    })
    return s

def fetch_finished(session: requests.Session, date_from: date, date_to: date, competitions: Optional[str]) -> List[Dict[str, Any]]:
    params = {
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "status": "FINISHED",
    }
    if competitions:
        params["competitions"] = competitions
    url = f"{BASE}/matches?{urllib.parse.urlencode(params)}"
    r = session.get(url, timeout=30, allow_redirects=True)
    if not r.ok:
        sys.stderr.write(f"[fdo-res] HTTP {r.status_code} url={r.url} body={r.text[:300]}\n")
        r.raise_for_status()
    payload = r.json()
    return payload.get("matches", [])

def chunked_date_ranges(date_from: date, date_to: date, chunk_days: int = 10):
    cur = date_from
    while cur <= date_to:
        end = min(date_to, cur + timedelta(days=chunk_days))
        yield cur, end
        # FDO richiede periodo NON superiore a 10 giorni, quindi facciamo avanzare di chunk_days
        cur = end + timedelta(days=1)

def main():
    token = clean(os.environ.get("FOOTBALL_DATA_API_KEY",""))
    if not token:
        sys.stderr.write("[fdo-res] FOOTBALL_DATA_API_KEY non impostata (.env)\n")
        sys.exit(1)

    back_days = int(os.environ.get("FETCH_BACK_DAYS","180"))
    competitions = os.environ.get("LEAGUE_CODES","").strip()  # es "PL,SA,PD"
    chunk_days = int(os.environ.get("FDO_CHUNK_DAYS", "10"))  # massimo 10
    data_dir = Path(os.environ.get("DATA_DIR","data"))
    out_file = data_dir / "history" / "results.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=back_days)
    date_to = today

    s = new_session(token)
    print(f"[fdo-res] dateFrom={date_from} dateTo={date_to} comps={competitions or 'ALL'} chunk={chunk_days}d")

    all_matches: List[Dict[str, Any]] = []
    seen_ids = set()

    for df, dt in chunked_date_ranges(date_from, date_to, chunk_days=chunk_days):
        try:
            matches = fetch_finished(s, df, dt, competitions or None)
        except Exception as e:
            sys.stderr.write(f"[fdo-res] errore fetch chunk {df}..{dt}: {e}\n")
            continue
        # dedup per id
        for m in matches:
            mid = m.get("id")
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            all_matches.append(m)
        # rispetto rate-limit free
        time.sleep(0.4)

    cnt = 0
    with out_file.open("w", encoding="utf-8") as f:
        for m in all_matches:
            rec = {
                "id": m.get("id"),
                "utcDate": m.get("utcDate"),
                "competition": (m.get("competition") or {}).get("code") or (m.get("competition") or {}).get("name"),
                "home": (m.get("homeTeam") or {}).get("name"),
                "away": (m.get("awayTeam") or {}).get("name"),
                "fullTime": ((m.get("score") or {}).get("fullTime") or {}),
                "status": m.get("status"),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cnt += 1

    print(f"[fdo-res] Scritti {cnt} risultati in {out_file}")

if __name__ == "__main__":
    main()
