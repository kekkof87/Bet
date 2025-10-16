#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
import urllib.request

API_BASE = "https://v3.football.api-sports.io"

def http_get(url: str, headers: Dict[str, str], timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)

def save_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def main():
    api_key = os.environ.get("APIFOOTBALL_API_KEY")
    if not api_key:
        print("[fixtures] APIFOOTBALL_API_KEY non impostata", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    today = datetime.now(timezone.utc).date()
    date_from = today
    date_to = today + timedelta(days=2)

    headers = {
        "x-apisports-key": api_key,
        "Accept": "application/json",
        "User-Agent": "betting-dashboard/1.0",
    }
    url = f"{API_BASE}/fixtures?from={date_from.isoformat()}&to={date_to.isoformat()}"

    try:
        payload = http_get(url, headers=headers)
    except Exception as e:
        print(f"[fixtures] errore HTTP: {e}", file=sys.stderr)
        sys.exit(2)

    resp = payload.get("response", [])
    items: List[Dict[str, Any]] = []
    for r in resp:
        try:
            fx = r.get("fixture", {})
            lg = r.get("league", {})
            tm = r.get("teams", {})
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

    # Scrivi sia last_delta.json che fixtures.json
    save_json(data_dir / "last_delta.json", {"added": items})
    save_json(data_dir / "fixtures.json", {"generated_from": "apifootball", "count": len(items), "items": items})

    print(f"[fixtures] Scritti {len(items)} fixtures in data/fixtures.json e data/last_delta.json")

if __name__ == "__main__":
    main()
