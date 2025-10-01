from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("analytics.roi")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json_atomic(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _outcome_from_scores(home_score: Any, away_score: Any) -> Optional[str]:
    try:
        hs = int(home_score)
        as_ = int(away_score)
    except Exception:
        return None
    if hs > as_:
        return "home_win"
    if hs < as_:
        return "away_win"
    return "draw"


def load_fixtures_map(fixtures: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for fx in fixtures:
        fid = fx.get("fixture_id")
        if isinstance(fid, int):
            out[fid] = fx
    return out


def load_value_alerts() -> List[Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.value_alerts_dir / "value_alerts.json"
    raw = _load_json(path)
    if not raw:
        return []
    al = raw.get("alerts")
    if not isinstance(al, list):
        return []
    clean = []
    for a in al:
        if isinstance(a, dict) and a.get("fixture_id") is not None and a.get("value_edge") is not None:
            clean.append(a)
    return clean


def load_predictions_index() -> Dict[int, Dict[str, Any]]:
    """
    Carica predictions/latest_predictions.json e indicizza per fixture_id.
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.predictions_dir / "latest_predictions.json"
    raw = _load_json(path)
    if not raw:
        return {}
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for p in preds:
        if isinstance(p, dict) and isinstance(p.get("fixture_id"), int):
            out[p["fixture_id"]] = p
    return out


def load_consensus_index() -> Dict[int, Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.consensus_dir / "consensus.json"
    raw = _load_json(path)
    if not raw:
        return {}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        if isinstance(e, dict) and isinstance(e.get("fixture_id"), int):
            out[e["fixture_id"]] = e
    return out


def load_odds_latest_index() -> Dict[int, Dict[str, Any]]:
    """
    odds_latest.json:
    {
      "provider": "...",
      "entries": [
         {"fixture_id": X, "market": {"home_win": 2.1, "draw": 3.3, "away_win": 3.4}, ...}
      ]
    }
    """
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.odds_dir / "odds_latest.json"
    raw = _load_json(path)
    if not raw:
        return {}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        if isinstance(e, dict) and isinstance(e.get("fixture_id"), int):
            out[e["fixture_id"]] = e
    return out


def load_ledger(base: Path) -> List[Dict[str, Any]]:
    p = base / "ledger.json"
    raw = _load_json(p)
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    return []


def save_ledger(base: Path, ledger: List[Dict[str, Any]]) -> None:
    _save_json_atomic(base / "ledger.json", ledger)


def compute_metrics(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [p for p in ledger if p.get("settled")]
    won = [p for p in settled if p.get("result") == "win"]
    lost = [p for p in settled if p.get("result") == "loss"]

    profit = 0.0
    for p in settled:
        stake = float(p.get("stake", 1.0))
        if p.get("result") == "win":
            profit += float(p.get("payout", 0.0)) - stake
        elif p.get("result") == "loss":
            profit -= stake

    total_stake = sum(float(p.get("stake", 1.0)) for p in settled)
    yield_pct = (profit / total_stake) if total_stake > 0 else 0.0
    hit_rate = (len(won) / len(settled)) if settled else 0.0

    return {
        "generated_at": _now_iso(),
        "total_picks": len(ledger),
        "settled_picks": len(settled),
        "open_picks": len([p for p in ledger if not p.get("settled")]),
        "wins": len(won),
        "losses": len(lost),
        "profit_units": round(profit, 6),
        "yield": round(yield_pct, 6),
        "hit_rate": round(hit_rate, 6),
    }


def save_metrics(base: Path, metrics: Dict[str, Any]) -> None:
    _save_json_atomic(base / "roi_metrics.json", metrics)


def _find_decimal_odds(
    fid: int,
    side: str,
    odds_latest_index: Dict[int, Dict[str, Any]],
    predictions_index: Dict[int, Dict[str, Any]],
) -> Tuple[float, str]:
    """
    Ritorna (decimal_odds, source_tag).
    Priorità:
      1. odds_latest.json (market)
      2. predictions.latest (pred['odds']['odds_original'])
      3. fallback 2.0
    """
    # 1: odds_latest
    entry = odds_latest_index.get(fid)
    if entry:
        market = entry.get("market")
        if isinstance(market, dict):
            val = market.get(side)
            if isinstance(val, (int, float)) and val > 1.01:
                return float(val), "odds_latest"

    # 2: predictions
    pred = predictions_index.get(fid)
    if pred:
        odds_block = pred.get("odds")
        if isinstance(odds_block, dict):
            orig = odds_block.get("odds_original")
            if isinstance(orig, dict):
                val = orig.get(side)
                if isinstance(val, (int, float)) and val > 1.01:
                    return float(val), "predictions_odds"

    # fallback
    return 2.0, "fallback"


def build_or_update_roi(fixtures: List[Dict[str, Any]]) -> None:
    """
    ROI tracking con odds reali:
    - Genera nuove picks da value alerts (status NS, edge >= soglia).
    - Recupera decimal_odds da odds_latest oppure predictions odds_original.
    - Settle picks quando fixture FT.
    """
    settings = get_settings()
    if not settings.enable_roi_tracking:
        return

    base = Path(settings.bet_data_dir or "data") / settings.roi_dir
    base.mkdir(parents=True, exist_ok=True)

    ledger = load_ledger(base)
    ledger_index = {(p.get("fixture_id"), p.get("source")): p for p in ledger if p.get("fixture_id")}

    fixtures_map = load_fixtures_map(fixtures)
    alerts = load_value_alerts()

    min_edge = settings.roi_min_edge
    include_consensus = settings.roi_include_consensus
    stake_units = settings.roi_stake_units

    predictions_index = load_predictions_index()
    odds_latest_index = load_odds_latest_index()

    now_ts = _now_iso()

    # Creazione nuove picks
    for alert in alerts:
        fid = alert.get("fixture_id")
        source = str(alert.get("source"))
        value_type = alert.get("value_type")
        if source not in {"prediction", "consensus"}:
            continue
        if source == "consensus" and not include_consensus:
            continue
        try:
            edge = float(alert.get("value_edge", 0.0))
        except Exception:
            continue
        if edge < min_edge:
            continue
        if not isinstance(fid, int):
            continue
        fx = fixtures_map.get(fid)
        if not fx:
            continue
        if fx.get("status") != "NS":
            continue
        key = (fid, source)
        if key in ledger_index:
            continue
        side = alert.get("value_side")
        if not isinstance(side, str):
            continue

        decimal_odds, odds_src = _find_decimal_odds(fid, side, odds_latest_index, predictions_index)
        fair_prob = round(1 / decimal_odds, 6) if decimal_odds > 0 else 0.5

        pick = {
            "created_at": now_ts,
            "fixture_id": fid,
            "source": source,
            "value_type": value_type,
            "side": side,
            "edge": edge,
            "stake": stake_units,
            "decimal_odds": round(decimal_odds, 6),
            "est_odds": round(decimal_odds, 6),  # backward compatibility
            "fair_prob": fair_prob,
            "odds_source": odds_src,
            "settled": False,
        }
        ledger.append(pick)
        ledger_index[key] = pick

    # Settlement
    for p in ledger:
        if p.get("settled"):
            continue
        fid = p.get("fixture_id")
        if not isinstance(fid, int):
            continue
        fx = fixtures_map.get(fid)
        if not fx or fx.get("status") != "FT":
            continue
        outcome = _outcome_from_scores(fx.get("home_score"), fx.get("away_score"))
        if not outcome:
            continue
        side = p.get("side")
        stake = float(p.get("stake", 1.0))
        decimal_odds = float(p.get("decimal_odds", 2.0))
        if side == outcome:
            p["result"] = "win"
            p["payout"] = round(decimal_odds * stake, 6)
        else:
            p["result"] = "loss"
            p["payout"] = 0.0
        p["settled"] = True
        p["settled_at"] = now_ts

    save_ledger(base, ledger)
    metrics = compute_metrics(ledger)
    save_metrics(base, metrics)
    logger.info(
        "roi_updated",
        extra={
            "picks": metrics["total_picks"],
            "settled": metrics["settled_picks"],
            "profit": metrics["profit_units"],
        },
    )


def load_roi_summary() -> Optional[Dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_roi_tracking:
        return None
    base = Path(settings.bet_data_dir or "data") / settings.roi_dir
    metrics = _load_json(base / "roi_metrics.json")
    if not metrics:
        return None
    return metrics


def load_roi_ledger() -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_roi_tracking:
        return []
    base = Path(settings.bet_data_dir or "data") / settings.roi_dir
    return load_ledger(base)
