import os
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone, timedelta

from core.config import _reset_settings_cache_for_tests, get_settings
from analytics.roi import build_or_update_roi, load_roi_summary, load_roi_ledger, load_roi_timeline_raw, load_roi_daily


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_alert(fid: int, source: str, edge: float, side: str = "home_win") -> Dict:
    return {
        "fixture_id": fid,
        "source": source,
        "value_edge": edge,
        "value_side": side,
        "value_type": "standard",
    }


def _gen_alerts() -> List[Dict]:
    alerts = []
    edges = [0.05,0.06,0.07,0.08,0.09,0.11,0.12,0.13,0.14,0.15,0.16,0.17]
    sources = ["prediction","consensus","merged"]
    for i, edge in enumerate(edges, start=1):
        source = sources[i % 3]
        side = "home_win" if i % 2 else "away_win"
        alerts.append(_make_alert(1000 + i, source, edge, side))
    return alerts


def _prepare_input_files(base: Path):
    # value alerts
    _write_json(base / "value_alerts" / "value_alerts.json", {
        "alerts": _gen_alerts(),
        "effective_threshold": 0.05
    })

    # predictions
    preds = []
    for i in range(1,13):
        fid = 1000 + i
        preds.append({
            "fixture_id": fid,
            "prob": {
                "home_win": 0.45 + (i*0.002),
                "draw": 0.25,
                "away_win": 0.30 - (i*0.002)
            },
            "odds": {
                "odds_original": {
                    "home_win": 2.0,
                    "draw": 3.4,
                    "away_win": 2.5
                }
            }
        })
    _write_json(base / "predictions" / "latest_predictions.json", {"predictions": preds})

    # consensus
    entries = []
    for i in range(1,13):
        fid = 1000 + i
        entries.append({
            "fixture_id": fid,
            "blended_prob": {
                "home_win": 0.44 + (i*0.002),
                "draw": 0.26,
                "away_win": 0.30 - (i*0.002)
            }
        })
    _write_json(base / "consensus" / "consensus.json", {"entries": entries})

    # odds_latest
    odds_entries = []
    for i in range(1,13):
        fid = 1000 + i
        odds_entries.append({
            "fixture_id": fid,
            "market": {
                "home_win": 2.0 + (i*0.01),
                "draw": 3.4,
                "away_win": 2.5 - (i*0.01)
            },
            "source": "stub-book"
        })
    _write_json(base / "odds" / "odds_latest.json", {"entries": odds_entries})


def _fixtures(status: str) -> List[Dict]:
    fixes = []
    for i in range(1,13):
        fid = 1000 + i
        if status == "FT":
            home = (i % 3) + 1
            away = (i % 2)
        else:
            home = 0
            away = 0
        fixes.append({
            "fixture_id": fid,
            "status": status,
            "home_score": home,
            "away_score": away,
            "league_id": 200 + (i % 4),
        })
    return fixes


def _seed_old_ledger_for_pruning(roi_dir: Path):
    """
    Crea un ledger.json con un pick vecchio (30 giorni) e uno recente
    per coprire il ramo di pruning per età e generare archive stats.
    """
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent_date = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    ledger = [
        {
            "created_at": old_date,
            "fixture_id": 9001,
            "source": "prediction",
            "value_type": "standard",
            "side": "home_win",
            "edge": 0.06,
            "stake": 1.0,
            "stake_strategy": "fixed",
            "decimal_odds": 2.0,
            "est_odds": 2.0,
            "fair_prob": 0.5,
            "odds_source": "fallback",
            "settled": True,
            "result": "win",
            "payout": 2.0,
            "settled_at": old_date
        },
        {
            "created_at": recent_date,
            "fixture_id": 9002,
            "source": "prediction",
            "value_type": "standard",
            "side": "away_win",
            "edge": 0.07,
            "stake": 1.0,
            "stake_strategy": "fixed",
            "decimal_odds": 2.1,
            "est_odds": 2.1,
            "fair_prob": 0.48,
            "odds_source": "fallback",
            "settled": False
        }
    ]
    _write_json(roi_dir / "ledger.json", ledger)

    # Seed archive to trigger archive_stats path (non vuoto)
    archive = [
        {
            "created_at": (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(),
            "fixture_id": 8001,
            "source": "prediction",
            "value_type": "standard",
            "side": "draw",
            "edge": 0.08,
            "stake": 1.0,
            "stake_strategy": "fixed",
            "decimal_odds": 3.4,
            "est_odds": 3.4,
            "fair_prob": 0.30,
            "odds_source": "fallback",
            "settled": True,
            "result": "loss",
            "payout": 0.0,
            "settled_at": (datetime.now(timezone.utc) - timedelta(days=39)).isoformat()
        }
    ]
    _write_json(roi_dir / "ledger_archive.json", archive)


def test_regime_m1_full_coverage(tmp_path: Path, monkeypatch):
    # ENV base obbligatorio
    os.environ["API_FOOTBALL_KEY"] = "DUMMY_KEY"

    data_dir = tmp_path / "data"
    os.environ["BET_DATA_DIR"] = str(data_dir)

    # Core ROI
    os.environ["ENABLE_ROI_TRACKING"] = "1"
    os.environ["ENABLE_ROI_REGIME"] = "1"
    os.environ["ROI_REGIME_VERSION"] = "m1"
    os.environ["ENABLE_ROI_REGIME_PERSISTENCE"] = "1"

    # Regime params
    os.environ["ROI_REGIME_MIN_POINTS"] = "20"
    os.environ["ROI_REGIME_MIN_HOLD"] = "2"
    os.environ["ROI_REGIME_SMOOTH_ALPHA"] = "0.5"
    os.environ["ROI_REGIME_MOM_THRESHOLD"] = "0.0015"
    os.environ["ROI_REGIME_MOMENTUM_WINDOWS"] = "5,10,30"
    os.environ["ROI_REGIME_HISTORY_MAX"] = "10"

    # Pruning & archive coverage
    os.environ["ROI_LEDGER_MAX_AGE_DAYS"] = "5"
    os.environ["ENABLE_ROI_ARCHIVE_STATS"] = "1"

    # Advanced blocks
    os.environ["ENABLE_ROI_KELLY_EFFECT"] = "1"
    os.environ["ENABLE_ROI_PAYOUT_MOMENTS"] = "1"
    os.environ["ENABLE_ROI_PROFIT_BUCKETS"] = "1"
    os.environ["ROI_PROFIT_BUCKETS"] = "-2--1,-1--0.5,-0.5-0,0-0.5,0.5-1,1-"
    os.environ["ENABLE_ROI_MONTECARLO"] = "1"
    os.environ["ROI_MC_RUNS"] = "25"
    os.environ["ROI_MC_WINDOW"] = "60"
    os.environ["ENABLE_ROI_MARKET_PLACEHOLDER"] = "1"
    os.environ["ENABLE_ROI_COMPACT_EXPORT"] = "1"
    os.environ["ENABLE_ROI_AGING_BUCKETS"] = "1"
    os.environ["ROI_AGING_BUCKETS"] = "1,2,3"
    os.environ["ENABLE_ROI_CLV_BUCKETS"] = "1"
    os.environ["ROI_CLV_BUCKETS"] = "-0.05-0,0-0.05,0.05-0.1,0.1-"
    os.environ["ENABLE_ROI_SIDE_BREAKDOWN"] = "1"
    os.environ["ENABLE_ROI_EQUITY_VOL"] = "1"
    os.environ["ROI_EQUITY_VOL_WINDOWS"] = "10,30"
    os.environ["ENABLE_ROI_ANOMALY_FLAGS"] = "1"
    os.environ["ENABLE_ROI_SOURCE_EFFICIENCY"] = "1"
    os.environ["ENABLE_ROI_EDGE_CLV_CORR"] = "1"
    os.environ["ENABLE_ROI_STAKE_ADVISORY"] = "1"
    os.environ["ENABLE_ROI_PROFIT_DISTRIBUTION"] = "1"
    os.environ["ENABLE_ROI_SCHEMA_EXPORT"] = "1"  # copre export schema

    # Reset settings cache
    _reset_settings_cache_for_tests()
    s = get_settings()
    assert s.enable_roi_regime

    _prepare_input_files(data_dir)

    # Seed ledger + archive BEFORE first run (pruning + archive_stats)
    roi_dir = data_dir / s.roi_dir
    roi_dir.mkdir(parents=True, exist_ok=True)
    _seed_old_ledger_for_pruning(
