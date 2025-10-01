from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    al = raw.get("alerts")
    if not isinstance(al, list):
        return []
    clean = []
    for a in al:
        if isinstance(a, dict) and a.get("value_edge") is not None and a.get("fixture_id") is not None:
            clean.append(a)
    return clean


def load_ledger(base: Path) -> List[Dict[str, Any]]:
    p = base / "ledger.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        return []
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


def build_or_update_roi(fixtures: List[Dict[str, Any]]) -> None:
    """
    Stub ROI tracking:
    - Genera picks da value_alerts (solo status NS, edge >= soglia)
    - Settle picks quando status diventa FT
    - Stake fisso, odds stimate placeholder (2.0) -> TODO: sostituire con odds reali
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

    now_ts = _now_iso()

    # Crea nuove picks
    for alert in alerts:
        fid = alert.get("fixture_id")
        source = str(alert.get("source"))
        value_type = alert.get("value_type")
        if source not in {"prediction", "consensus"}:
            continue
        if source == "consensus" and not include_consensus:
            continue
        edge = float(alert.get("value_edge", 0.0))
        if edge < min_edge:
            continue
        fx = fixtures_map.get(int(fid)) if isinstance(fid, int) else None
        if not fx:
            continue
        status = fx.get("status")
        if status != "NS":
            continue
        key = (fid, source)
        if key in ledger_index:
            continue
        side = alert.get("value_side")
        # TODO: integrare odds reali -> per ora odds stimata = 2.0
        est_odds = 2.0
        pick = {
            "created_at": now_ts,
            "fixture_id": fid,
            "source": source,
            "value_type": value_type,
            "side": side,
            "edge": edge,
            "stake": stake_units,
            "est_odds": est_odds,
            "settled": False,
        }
        ledger.append(pick)
        ledger_index[key] = pick

    # Settle picks
    for p in ledger:
        if p.get("settled"):
            continue
        fid = p.get("fixture_id")
        fx = fixtures_map.get(int(fid)) if isinstance(fid, int) else None
        if not fx or fx.get("status") != "FT":
            continue
        outcome = _outcome_from_scores(fx.get("home_score"), fx.get("away_score"))
        if not outcome:
            continue
        side = p.get("side")
        stake = float(p.get("stake", 1.0))
        est_odds = float(p.get("est_odds", 2.0))
        if side == outcome:
            p["result"] = "win"
            p["payout"] = round(est_odds * stake, 6)
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
        extra={"picks": metrics["total_picks"], "settled": metrics["settled_picks"]},
    )
