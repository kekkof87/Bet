from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

from .http_client import FootballDataClient


FD_STATUS_MAP = {
    "SCHEDULED": "NS",
    "TIMED": "NS",
    "IN_PLAY": "1H",  # senza minuto distinto assumiamo 1H
    "PAUSED": "HT",
    "FINISHED": "FT",
    "POSTPONED": "PST",
    "SUSPENDED": "PST",
    "CANCELED": "PST",
}


def _map_status(fd_status: Optional[str], minute: Optional[int]) -> str:
    if not fd_status:
        return "NS"
    s = FD_STATUS_MAP.get(fd_status, "NS")
    if fd_status == "IN_PLAY" and isinstance(minute, int):
        return "2H" if minute > 45 else "1H"
    return s


def _extract_score(m: Dict[str, Any]) -> Dict[str, Optional[int]]:
    score = (m.get("score") or {})
    # preferisci regularTime > fullTime > halfTime
    for key in ("regularTime", "fullTime", "halfTime"):
        blk = score.get(key)
        if isinstance(blk, dict):
            h = blk.get("home")
            a = blk.get("away")
            return {
                "home": int(h) if isinstance(h, int) else None,
                "away": int(a) if isinstance(a, int) else None,
            }
    return {"home": None, "away": None}


def _to_int_season(m: Dict[str, Any]) -> int:
    season = m.get("season") or {}
    # es: {"startDate": "2024-08-01", "endDate": "..."}
    start = season.get("startDate")
    if isinstance(start, str) and len(start) >= 4 and start[:4].isdigit():
        return int(start[:4])
    return 0


def _normalize(m: Dict[str, Any]) -> Dict[str, Any]:
    minute = m.get("minute")
    status = _map_status(m.get("status"), minute if isinstance(minute, int) else None)
    comp = m.get("competition") or {}
    score = _extract_score(m)
    home = m.get("homeTeam") or {}
    away = m.get("awayTeam") or {}
    return {
        "fixture_id": int(m.get("id")),  # FD usa int id
        "league_id": comp.get("code") or "",  # string code (PL, SA, ...)
        "league_name": comp.get("name") or "",
        "season": _to_int_season(m),
        "date_utc": m.get("utcDate"),
        "home_team": home.get("shortName") or home.get("name") or "",
        "away_team": away.get("shortName") or away.get("name") or "",
        "status": status,
        "home_score": score["home"],
        "away_score": score["away"],
        "provider": "football-data",
    }


class FootballDataFixturesProvider:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.client = FootballDataClient(api_key=api_key)

    @staticmethod
    def _competitions_csv() -> str:
        # default: PL, BL1, SA, PD, FL1, CL, EL, ECL
        csv = (os.getenv("FOOTBALL_DATA_LEAGUES") or "").strip()
        if not csv:
            csv = "PL,BL1,SA,PD,FL1,CL,EL,ECL"
        return csv

    def fetch_live(self) -> List[Dict[str, Any]]:
        params = {"status": "LIVE", "competitions": self._competitions_csv()}
        data = self.client.get("/matches", params=params)
        matches = data.get("matches") or []
        return [_normalize(m) for m in matches if isinstance(m, dict)]

    def fetch_upcoming_range(self, date_from_iso: str, date_to_iso: str) -> List[Dict[str, Any]]:
        params = {
            "dateFrom": date_from_iso[:10],
            "dateTo": date_to_iso[:10],
            "competitions": self._competitions_csv(),
        }
        data = self.client.get("/matches", params=params)
        matches = data.get("matches") or []
        return [_normalize(m) for m in matches if isinstance(m, dict)]

    def fetch_upcoming_days(self, days: int = 2) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=max(1, days))
        return self.fetch_upcoming_range(now.isoformat(), end.isoformat())

    def get_standings_map(self, competition_code: str) -> Dict[str, float]:
        # ritorna mappa team_name -> rating (z-score sui PPG)
        data = self.client.get(f"/competitions/{competition_code}/standings")
        standings = data.get("standings") or []
        total_blk: Dict[str, Any] = next((s for s in standings if s.get("type") == "TOTAL"), {})  # type: ignore[assignment]
        table = total_blk.get("table") or []
        ppg_items: List[Dict[str, Any]] = []
        for row in table:
            played = int(row.get("playedGames") or 0)
            pts = int(row.get("points") or 0)
            team = (row.get("team") or {}).get("shortName") or (row.get("team") or {}).get("name") or ""
            ppg = (pts / played) if played > 0 else 1.2
            ppg_items.append({"team": team, "ppg": ppg})
        if not ppg_items:
            return {}
        mean = sum(x["ppg"] for x in ppg_items) / len(ppg_items)
        var = sum((x["ppg"] - mean) ** 2 for x in ppg_items) / len(ppg_items)
        std = var ** 0.5 or 1.0
        ratings: Dict[str, float] = {}
        for x in ppg_items:
            ratings[x["team"]] = (x["ppg"] - mean) / std
        return ratings

    def get_all_ratings(self) -> Dict[str, Dict[str, float]]:
        csv = self._competitions_csv()
        out: Dict[str, Dict[str, float]] = {}
        for code in [c.strip() for c in csv.split(",") if c.strip()]:
            try:
                out[code] = self.get_standings_map(code)
            except Exception:
                out[code] = {}
        return out
