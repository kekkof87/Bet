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


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


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
    return [a for a in al if isinstance(a, dict) and a.get("fixture_id") is not None and a.get("value_edge") is not None]


def load_predictions_index() -> Dict[int, Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.predictions_dir / "latest_predictions.json"
    raw = _load_json(path)
    if not raw:
        return {}
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        return {}
    return {p["fixture_id"]: p for p in preds if isinstance(p, dict) and isinstance(p.get("fixture_id"), int)}


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
    return {e["fixture_id"]: e for e in entries if isinstance(e, dict) and isinstance(e.get("fixture_id"), int)}


def load_odds_latest_index() -> Dict[int, Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    path = base / settings.odds_dir / "odds_latest.json"
    raw = _load_json(path)
    if not raw:
        return {}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {}
    return {e["fixture_id"]: e for e in entries if isinstance(e, dict) and isinstance(e.get("fixture_id"), int)}


def load_ledger(base: Path) -> List[Dict[str, Any]]:
    p = base / "ledger.json"
    raw = _load_json(p)
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    return []


def save_ledger(base: Path, ledger: List[Dict[str, Any]]) -> None:
    _save_json_atomic(base / "ledger.json", ledger)


def _compute_profit_and_stats(picks: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [p for p in picks if p.get("settled")]
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
        "picks": len(picks),
        "settled": len(settled),
        "open": len([p for p in picks if not p.get("settled")]),
        "wins": len(won),
        "losses": len(lost),
        "profit_units": round(profit, 6),
        "yield": round(yield_pct, 6),
        "hit_rate": round(hit_rate, 6),
        "stake_sum": round(total_stake, 6),
    }


def _equity_stats(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcola drawdown e picchi su sequenza dei profitti cumulativi dei pick SETTLED in ordine cronologico (created_at).
    Profit step: aggiornato dopo ogni pick settled (win: +payout - stake, loss: -stake).
    """
    settled = [p for p in ledger if p.get("settled")]
    if not settled:
        return {
            "peak_profit": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "current_drawdown": 0.0,
            "current_drawdown_pct": 0.0,
            "equity_points": 0,
        }
    # Ordina per created_at per coerenza temporale
    settled.sort(key=lambda x: x.get("created_at") or "")
    equity = []
    running = 0.0
    max_peak = 0.0
    max_dd = 0.0
    for p in settled:
        stake = float(p.get("stake", 1.0))
        if p.get("result") == "win":
            running += float(p.get("payout", 0.0)) - stake
        elif p.get("result") == "loss":
            running -= stake
        # aggiorna peak / drawdown
        if running > max_peak:
            max_peak = running
        drawdown = max_peak - running
        if drawdown > max_dd:
            max_dd = drawdown
        equity.append(running)
    peak_profit = round(max_peak, 6)
    max_drawdown = round(max_dd, 6)
    max_drawdown_pct = round(max_drawdown / peak_profit, 6) if peak_profit > 0 else 0.0
    current_drawdown = round(max_peak - equity[-1], 6)
    current_drawdown_pct = round(current_drawdown / peak_profit, 6) if peak_profit > 0 else 0.0
    return {
        "peak_profit": peak_profit,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "current_drawdown": current_drawdown,
        "current_drawdown_pct": current_drawdown_pct,
        "equity_points": len(equity),
    }


def compute_metrics(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    global_stats = _compute_profit_and_stats(ledger)
    pred_stats = _compute_profit_and_stats([p for p in ledger if p.get("source") == "prediction"])
    cons_stats = _compute_profit_and_stats([p for p in ledger if p.get("source") == "consensus"])
    eq = _equity_stats(ledger)

    return {
        "generated_at": _now_iso(),
        "total_picks": global_stats["picks"],
        "settled_picks": global_stats["settled"],
        "open_picks": global_stats["open"],
        "wins": global_stats["wins"],
        "losses": global_stats["losses"],
        "profit_units": global_stats["profit_units"],
        "yield": global_stats["yield"],
        "hit_rate": global_stats["hit_rate"],
        # source breakdown
        "picks_prediction": pred_stats["picks"],
        "settled_prediction": pred_stats["settled"],
        "open_prediction": pred_stats["open"],
        "wins_prediction": pred_stats["wins"],
        "losses_prediction": pred_stats["losses"],
        "profit_units_prediction": pred_stats["profit_units"],
        "yield_prediction": pred_stats["yield"],
        "hit_rate_prediction": pred_stats["hit_rate"],
        "picks_consensus": cons_stats["picks"],
        "settled_consensus": cons_stats["settled"],
        "open_consensus": cons_stats["open"],
        "wins_consensus": cons_stats["wins"],
        "losses_consensus": cons_stats["losses"],
        "profit_units_consensus": cons_stats["profit_units"],
        "yield_consensus": cons_stats["yield"],
        "hit_rate_consensus": cons_stats["hit_rate"],
        # equity / drawdown
        "peak_profit": eq["peak_profit"],
        "max_drawdown": eq["max_drawdown"],
        "max_drawdown_pct": eq["max_drawdown_pct"],
        "current_drawdown": eq["current_drawdown"],
        "current_drawdown_pct": eq["current_drawdown_pct"],
        "equity_points": eq["equity_points"],
    }


def save_metrics(base: Path, metrics: Dict[str, Any]) -> None:
    _save_json_atomic(base / "roi_metrics.json", metrics)


def _find_decimal_odds(
    fid: int,
    side: str,
    odds_latest_index: Dict[int, Dict[str, Any]],
    predictions_index: Dict[int, Dict[str, Any]],
) -> Tuple[float, str]:
    entry = odds_latest_index.get(fid)
    if entry:
        market = entry.get("market")
        if isinstance(market, dict):
            val = market.get(side)
            if isinstance(val, (int, float)) and val > 1.01:
                return float(val), "odds_latest"
    pred = predictions_index.get(fid)
    if pred:
        odds_block = pred.get("odds")
        if isinstance(odds_block, dict):
            orig = odds_block.get("odds_original")
            if isinstance(orig, dict):
                val = orig.get(side)
                if isinstance(val, (int, float)) and val > 1.01:
                    return float(val), "predictions_odds"
    return 2.0, "fallback"


def _append_timeline(base: Path, metrics: Dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.enable_roi_timeline:
        return
    history_path = base / settings.roi_timeline_file
    daily_path = base / settings.roi_daily_file
    record = {
        "ts": metrics.get("generated_at"),
        "total_picks": metrics.get("total_picks"),
        "settled_picks": metrics.get("settled_picks"),
        "profit_units": metrics.get("profit_units"),
        "yield": metrics.get("yield"),
        "hit_rate": metrics.get("hit_rate"),
    }
    try:
        _append_jsonl(history_path, record)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore append ROI timeline: %s", exc)
    day = _utc_day()
    daily = _load_json(daily_path) or {}
    if not isinstance(daily, dict):
        daily = {}
    d_entry = daily.get(day, {})
    runs = int(d_entry.get("runs", 0)) + 1
    daily[day] = {
        "last_ts": record["ts"],
        "runs": runs,
        "total_picks": record["total_picks"],
        "settled_picks": record["settled_picks"],
        "profit_units": record["profit_units"],
        "yield": record["yield"],
        "hit_rate": record["hit_rate"],
    }
    try:
        _save_json_atomic(daily_path, daily)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore salvataggio daily ROI: %s", exc)


def _extract_side_prob(pred_or_cons: Dict[str, Any], side: str, source: str) -> Optional[float]:
    key = "prob" if source == "prediction" else "blended_prob"
    block = pred_or_cons.get(key)
    if not isinstance(block, dict):
        return None
    val = block.get(side)
    if isinstance(val, (int, float)) and 0 <= val <= 1:
        return float(val)
    return None


def _compute_kelly_stake(
    *,
    decimal_odds: float,
    model_prob: Optional[float],
    base_units: float,
    max_units: float,
    fraction_cap: float,
) -> Tuple[float, Optional[float], Optional[float], Optional[float], Optional[float]]:
    if model_prob is None or model_prob <= 0 or model_prob >= 1:
        return base_units, None, None, model_prob, decimal_odds - 1
    b = decimal_odds - 1
    if b <= 0:
        return base_units, None, None, model_prob, b
    fraction = (decimal_odds * model_prob - 1) / b
    if fraction <= 0:
        return base_units, fraction, None, model_prob, b
    fraction_capped = min(fraction, fraction_cap)
    stake = fraction_capped * base_units
    stake = min(stake, max_units)
    if stake < 0.0001:
        stake = 0.0001
    return round(stake, 6), round(fraction, 6), round(fraction_capped, 6), model_prob, b


def _build_snapshot(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_roi_odds_snapshot:
        return None
    market = entry.get("market")
    if not isinstance(market, dict):
        return None
    base_outcomes = {}
    for k in ("home_win", "draw", "away_win"):
        v = market.get(k)
        if isinstance(v, (int, float)) and v > 1.01:
            base_outcomes[k] = float(v)
    if not base_outcomes:
        return None
    implied_raw = {k: 1.0 / v for k, v in base_outcomes.items()}
    s = sum(implied_raw.values())
    implied_norm = {k: round(v / s, 6) for k, v in implied_raw.items()} if s > 0 else {}
    overround = round(s - 1.0, 6) if s > 0 else 0.0
    provider = entry.get("source") or entry.get("provider") or settings.odds_default_source
    return {
        "market_snapshot": base_outcomes,
        "snapshot_implied": implied_norm,
        "snapshot_overround": overround,
        "snapshot_provider": provider,
        "snapshot_at": _now_iso(),
    }


def build_or_update_roi(fixtures: List[Dict[str, Any]]) -> None:
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
    default_stake_units = settings.roi_stake_units

    predictions_index = load_predictions_index()
    consensus_index = load_consensus_index()
    odds_latest_index = load_odds_latest_index()

    now_ts = _now_iso()

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
        if not fx or fx.get("status") != "NS":
            continue
        key = (fid, source)
        if key in ledger_index:
            continue
        side = alert.get("value_side")
        if not isinstance(side, str):
            continue

        decimal_odds, odds_src = _find_decimal_odds(fid, side, odds_latest_index, predictions_index)
        fair_prob = round(1 / decimal_odds, 6) if decimal_odds > 0 else 0.5

        model_prob = None
        if source == "prediction":
            pred = predictions_index.get(fid)
            if pred:
                model_prob = _extract_side_prob(pred, side, "prediction")
        else:
            cons = consensus_index.get(fid)
            if cons:
                model_prob = _extract_side_prob(cons, side, "consensus")

        stake = default_stake_units
        stake_strategy = "fixed"
        kelly_fraction = None
        kelly_fraction_capped = None
        kelly_prob = None
        kelly_b = None

        if settings.enable_kelly_staking:
            stake_strategy = "kelly"
            stake, k_f, k_fc, kelly_prob, kelly_b = _compute_kelly_stake(
                decimal_odds=decimal_odds,
                model_prob=model_prob,
                base_units=settings.kelly_base_units,
                max_units=settings.kelly_max_units,
                fraction_cap=settings.kelly_edge_cap,
            )
            kelly_fraction = k_f
            kelly_fraction_capped = k_fc
            if kelly_fraction is None or kelly_fraction <= 0:
                stake_strategy = "fixed"

        snapshot_block = None
        entry = odds_latest_index.get(fid)
        if entry:
            snapshot_block = _build_snapshot(entry)

        pick = {
            "created_at": now_ts,
            "fixture_id": fid,
            "source": source,
            "value_type": value_type,
            "side": side,
            "edge": edge,
            "stake": stake,
            "stake_strategy": stake_strategy,
            "decimal_odds": round(decimal_odds, 6),
            "est_odds": round(decimal_odds, 6),
            "fair_prob": fair_prob,
            "odds_source": odds_src,
            "kelly_fraction": kelly_fraction,
            "kelly_fraction_capped": kelly_fraction_capped,
            "kelly_prob": kelly_prob,
            "kelly_b": kelly_b,
            "settled": False,
        }
        if snapshot_block:
            pick.update(snapshot_block)

        ledger.append(pick)
        ledger_index[key] = pick

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
        p["settled_at"] = _now_iso()

    save_ledger(base, ledger)
    metrics = compute_metrics(ledger)
    save_metrics(base, metrics)
    _append_timeline(base, metrics)

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


def load_roi_timeline_raw() -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_roi_tracking or not settings.enable_roi_timeline:
        return []
    base = Path(settings.bet_data_dir or "data") / settings.roi_dir
    path = base / settings.roi_timeline_file
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if isinstance(rec, dict):
                    out.append(rec)
            except Exception:
                continue
    except Exception:
        return []
    return out


def load_roi_daily() -> Dict[str, Any]:
    settings = get_settings()
    if not settings.enable_roi_tracking or not settings.enable_roi_timeline:
        return {}
    base = Path(settings.bet_data_dir or "data") / settings.roi_dir
    path = base / settings.roi_daily_file
    data = _load_json(path)
    if isinstance(data, dict):
        return data
    return {}
