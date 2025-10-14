from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, cast
from datetime import datetime, timezone

from core.config import get_settings
from core.logging import get_logger
from core.persistence import save_latest_fixtures
from core.models import FixtureDataset

from providers.api_football.fixtures_provider import ApiFootballFixturesProvider
from providers.football_data.fixtures_provider import FootballDataFixturesProvider

log = get_logger("scripts.fetch_fixtures")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_scoreboard(fixtures: FixtureDataset, live_ids: set[int]) -> Dict[str, Any]:
    now = _now_iso()
    total = len(fixtures)
    live_count = len(live_ids)
    upcoming_24 = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    in_24 = now_ts + 24 * 3600
    for f in fixtures:
        try:
            if f.get("status") == "NS":
                ts = datetime.fromisoformat(str(f.get("date_utc"))).timestamp()
                if now_ts <= ts <= in_24:
                    upcoming_24 += 1
        except Exception:
            pass
    return {
        "generated_at": now,
        "total": total,
        "live_count": live_count,
        "upcoming_count_next_24h": upcoming_24,
        "recent_delta": {"added": total, "removed": 0, "modified": 0},
        "change_breakdown": {"score_change": 0, "status_change": 0, "both": 0, "other": 0},
    }


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> None:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    base.mkdir(parents=True, exist_ok=True)

    provider_src = (os.getenv("PROVIDER_SOURCE") or "fd").lower().strip()
    upcoming_days = int(os.getenv("UPCOMING_DAYS") or "2")

    fixtures: FixtureDataset = []
    live_ids: set[int] = set()

    if provider_src == "api":
        api = ApiFootballFixturesProvider()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        league_id = settings.default_league_id
        season = settings.default_season
        has_specific_scope = (league_id is not None) or (season is not None)

        if has_specific_scope:
            # Fetch specifico per lega/stagione; NO fallback ad ALL se vuoto
            fixtures = cast(
                FixtureDataset,
                api.fetch_fixtures(date=today, league_id=league_id, season=season),
            )
            if not fixtures:
                log.info(
                    "No fixtures for specified league/season today; skipping ALL-LEAGUES fallback "
                    "(set PROVIDER_SOURCE=fd for the free provider or adjust defaults)."
                )
        else:
            # Nessuna lega/stagione specifica -> è lecito usare ALL LEAGUES
            fixtures = cast(FixtureDataset, api.fetch_fixtures(date=today, league_id=None, season=None))

        live_ids = {int(f.get("fixture_id")) for f in fixtures if f.get("status") in ("1H", "2H", "HT")}
    else:
        # Provider gratuito: football-data.org
        fd = FootballDataFixturesProvider()
        upcoming = fd.fetch_upcoming_days(days=upcoming_days)
        live = fd.fetch_live()
        by_id: Dict[int, Dict[str, Any]] = {}
        for f in upcoming + live:
            fid = int(f.get("fixture_id"))
            by_id[fid] = f
        fixtures = cast(FixtureDataset, list(by_id.values()))
        live_ids = {int(f.get("fixture_id")) for f in live}

    # Persist fixtures_latest
    save_latest_fixtures(fixtures)

    # Scoreboard
    scoreboard = _build_scoreboard(fixtures, live_ids)
    _write_json_atomic(base / "scoreboard.json", scoreboard)

    # Last run metrics (compat)
    last_run = {
        "summary": {"added": len(fixtures), "removed": 0, "modified": 0, "total_new": len(fixtures)},
        "change_breakdown": {"score_change": 0, "status_change": 0, "both": 0, "other": 0},
        "fetch_stats": {"attempts": 1, "retries": 0, "latency_ms": 0.0, "last_status": 200},
        "total_fixtures": len(fixtures),
    }
    _write_json_atomic(base / "metrics" / "last_run.json", last_run)

    log.info("fetch_complete", extra={"provider": provider_src, "fixtures": len(fixtures)})


if __name__ == "__main__":
    main()
