from __future__ import annotations

import csv
import json
import math
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("analytics.roi")


# -------------------- Time / I/O helpers --------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


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


# -------------------- Domain helpers --------------------
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
    return {
        fx["fixture_id"]: fx
        for fx in fixtures
        if isinstance(fx, dict) and isinstance(fx.get("fixture_id"), int)
    }


def load_value_alerts() -> List[Dict[str, Any]]:
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    path = base / s.value_alerts_dir / "value_alerts.json"
    raw = _load_json(path)
    if not raw:
        return []
    al = raw.get("alerts")
    if not isinstance(al, list):
        return []
    return [
        a
        for a in al
        if isinstance(a, dict)
        and a.get("fixture_id") is not None
        and a.get("value_edge") is not None
    ]


def load_predictions_index() -> Dict[int, Dict[str, Any]]:
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    path = base / s.predictions_dir / "latest_predictions.json"
    raw = _load_json(path)
    if not raw:
        return {}
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        return {}
    return {
        p["fixture_id"]: p
        for p in preds
        if isinstance(p, dict) and isinstance(p.get("fixture_id"), int)
    }


def load_consensus_index() -> Dict[int, Dict[str, Any]]:
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    path = base / s.consensus_dir / "consensus.json"
    raw = _load_json(path)
    if not raw:
        return {}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {}
    return {
        e["fixture_id"]: e
        for e in entries
        if isinstance(e, dict) and isinstance(e.get("fixture_id"), int)
    }


def load_odds_latest_index() -> Dict[int, Dict[str, Any]]:
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    path = base / s.odds_dir / "odds_latest.json"
    raw = _load_json(path)
    if not raw:
        return {}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        return {}
    return {
        e["fixture_id"]: e
        for e in entries
        if isinstance(e, dict) and isinstance(e.get("fixture_id"), int)
    }


def load_ledger(base: Path) -> List[Dict[str, Any]]:
    p = base / "ledger.json"
    raw = _load_json(p)
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    return []


def load_ledger_archive(base: Path) -> List[Dict[str, Any]]:
    p = base / "ledger_archive.json"
    raw = _load_json(p)
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    return []


def save_ledger(base: Path, ledger: List[Dict[str, Any]]) -> None:
    _save_json_atomic(base / "ledger.json", ledger)


def save_ledger_archive(base: Path, archive: List[Dict[str, Any]]) -> None:
    _save_json_atomic(base / "ledger_archive.json", archive)


# -------------------- Basic stats --------------------
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


def _profit_contribution(p: Dict[str, Any]) -> float:
    if not p.get("settled"):
        return 0.0
    stake = float(p.get("stake", 0.0))
    if p.get("result") == "win":
        return round(float(p.get("payout", 0.0)) - stake, 6)
    if p.get("result") == "loss":
        return round(-stake, 6)
    return 0.0


# -------------------- Equity & Drawdown --------------------
def _equity_stats(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    settled.sort(key=lambda x: x.get("created_at") or "")
    equity: List[float] = []
    running = 0.0
    max_peak = 0.0
    max_dd = 0.0
    for p in settled:
        contrib = _profit_contribution(p)
        running += contrib
        if running > max_peak:
            max_peak = running
        dd = max_peak - running
        if dd > max_dd:
            max_dd = dd
        equity.append(running)
    peak_profit = round(max_peak, 6)
    max_drawdown = round(max_dd, 6)
    max_drawdown_pct = round(max_drawdown / peak_profit, 6) if peak_profit > 0 else 0.0
    current_drawdown = round(max_peak - equity[-1], 6)
    current_drawdown_pct = (
        round(current_drawdown / peak_profit, 6) if peak_profit > 0 else 0.0
    )
    return {
        "peak_profit": peak_profit,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "current_drawdown": current_drawdown,
        "current_drawdown_pct": current_drawdown_pct,
        "equity_points": len(equity),
    }


# -------------------- Streaks --------------------
def _streak_stats(ledger: List[Dict[str, Any]]) -> Dict[str, int]:
    settled = [p for p in ledger if p.get("settled")]
    if not settled:
        return {
            "current_win_streak": 0,
            "current_loss_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
        }
    settled.sort(key=lambda x: x.get("created_at") or "")
    cw = cl = 0
    lw = ll = 0
    for p in settled:
        res = p.get("result")
        if res == "win":
            cw += 1
            cl = 0
            if cw > lw:
                lw = cw
        elif res == "loss":
            cl += 1
            cw = 0
            if cl > ll:
                ll = cl
        else:
            cw = 0
            cl = 0
    last = settled[-1].get("result")
    return {
        "current_win_streak": cw if last == "win" else 0,
        "current_loss_streak": cl if last == "loss" else 0,
        "longest_win_streak": lw,
        "longest_loss_streak": ll,
    }


# -------------------- Rolling (legacy single) --------------------
def _legacy_single_rolling(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    window = s.roi_rolling_window
    settled = [p for p in ledger if p.get("settled")]
    settled.sort(key=lambda x: x.get("created_at") or "")
    slice_set = settled[-window:] if settled else []
    profit = sum(_profit_contribution(p) for p in slice_set)
    total_stake = sum(float(p.get("stake", 1.0)) for p in slice_set)
    wins = sum(1 for p in slice_set if p.get("result") == "win")
    yield_pct = (profit / total_stake) if total_stake > 0 else 0.0
    hit_rate = wins / len(slice_set) if slice_set else 0.0
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in slice_set:
        running += _profit_contribution(p)
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return {
        "rolling_window_size": window,
        "picks_rolling": len(slice_set),
        "settled_rolling": len(slice_set),
        "profit_units_rolling": round(profit, 6),
        "yield_rolling": round(yield_pct, 6),
        "hit_rate_rolling": round(hit_rate, 6),
        "peak_profit_rolling": round(peak, 6),
        "max_drawdown_rolling": round(max_dd, 6),
    }


# -------------------- Rolling multi-window --------------------
def _rolling_window_stats_multi(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    settled = [p for p in ledger if p.get("settled")]
    settled.sort(key=lambda x: x.get("created_at") or "")
    result: Dict[str, Any] = {}
    for w in s.roi_rolling_windows:
        slice_set = settled[-w:] if settled else []
        profit = sum(_profit_contribution(p) for p in slice_set)
        total_stake = sum(float(p.get("stake", 1.0)) for p in slice_set)
        wins = sum(1 for p in slice_set if p.get("result") == "win")
        yield_pct = (profit / total_stake) if total_stake > 0 else 0.0
        hit_rate = wins / len(slice_set) if slice_set else 0.0
        running = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in slice_set:
            running += _profit_contribution(p)
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd
        result[f"w{w}"] = {
            "picks": len(slice_set),
            "profit_units": round(profit, 6),
            "yield": round(yield_pct, 6),
            "hit_rate": round(hit_rate, 6),
            "peak_profit": round(peak, 6),
            "max_drawdown": round(max_dd, 6),
        }
    return result


# -------------------- CLV aggregate --------------------
def _clv_aggregate(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_clv_aggregate:
        return {}
    settled = [
        p for p in ledger
        if p.get("settled") and isinstance(p.get("clv_pct"), (int, float))
    ]
    if not settled:
        return {
            "avg_clv_pct": None,
            "median_clv_pct": None,
            "realized_clv_win_avg": None,
            "realized_clv_loss_avg": None,
            "clv_positive_rate": None,
            "clv_realized_edge": None,
        }
    clvs = sorted(float(p["clv_pct"]) for p in settled)
    avg = sum(clvs) / len(clvs)
    m = len(clvs)
    median = clvs[m // 2] if m % 2 == 1 else (clvs[m // 2 - 1] + clvs[m // 2]) / 2
    wins = [float(p["clv_pct"]) for p in settled if p.get("result") == "win"]
    losses = [float(p["clv_pct"]) for p in settled if p.get("result") == "loss"]
    positive = sum(1 for v in clvs if v > 0)
    clv_positive_rate = positive / len(clvs) if clvs else 0.0
    return {
        "avg_clv_pct": round(avg, 6),
        "median_clv_pct": round(median, 6),
        "realized_clv_win_avg": round(sum(wins) / len(wins), 6) if wins else None,
        "realized_clv_loss_avg": round(sum(losses) / len(losses), 6) if losses else None,
        "clv_positive_rate": round(clv_positive_rate, 6),
    }


def _finalize_clv_block(clv_block: Dict[str, Any], global_yield: float) -> Dict[str, Any]:
    if clv_block.get("avg_clv_pct") is not None:
        clv_block["clv_realized_edge"] = round(clv_block["avg_clv_pct"] - global_yield, 6)
    else:
        clv_block["clv_realized_edge"] = None
    return clv_block


# -------------------- Edge deciles --------------------
def _edge_deciles(ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_edge_deciles:
        return []
    settled = [p for p in ledger if p.get("settled") and isinstance(p.get("edge"), (int, float))]
    if len(settled) < 5:
        if not settled:
            return []
        profit = sum(_profit_contribution(p) for p in settled)
        return [{
            "decile": 1,
            "edge_min": min(p["edge"] for p in settled),
            "edge_max": max(p["edge"] for p in settled),
            "picks": len(settled),
            "profit_units": round(profit, 6),
        }]
    edges = sorted(p["edge"] for p in settled)
    n = len(edges)
    dec_bounds = []
    for d in range(1, 11):
        idx = min(n - 1, int(d * n / 10) - 1)
        dec_bounds.append(edges[idx])

    def locate(val: float) -> int:
        for i, b in enumerate(dec_bounds):
            if val <= b:
                return i
        return 9

    acc: Dict[int, Dict[str, Any]] = {}
    for p in settled:
        di = locate(p["edge"])
        b = acc.setdefault(di, {
            "decile": di + 1,
            "edge_min": p["edge"],
            "edge_max": p["edge"],
            "picks": 0,
            "profit_units": 0.0
        })
        b["picks"] += 1
        if p["edge"] < b["edge_min"]:
            b["edge_min"] = p["edge"]
        if p["edge"] > b["edge_max"]:
            b["edge_max"] = p["edge"]
        b["profit_units"] = round(b["profit_units"] + _profit_contribution(p), 6)
    return [acc[i] for i in sorted(acc.keys())]


# -------------------- Source breakdown --------------------
def _source_breakdown(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_source_breakdown:
        return {}
    out: Dict[str, Any] = {}
    for src in ("prediction", "consensus", "merged"):
        picks_src = [p for p in ledger if p.get("source") == src]
        if picks_src:
            out[src] = _compute_profit_and_stats(picks_src)
    return out


# -------------------- Stake strategy breakdown --------------------
def _stake_breakdown(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_stake_breakdown:
        return {}
    kelly_picks = [p for p in ledger if p.get("stake_strategy") == "kelly"]
    fixed_picks = [p for p in ledger if p.get("stake_strategy") == "fixed"]
    out: Dict[str, Any] = {}
    if kelly_picks:
        out["kelly"] = _compute_profit_and_stats(kelly_picks)
    if fixed_picks:
        out["fixed"] = _compute_profit_and_stats(fixed_picks)
    return out


# -------------------- Risk metrics --------------------
def _risk_metrics(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_risk_metrics:
        return {}
    settled = [p for p in ledger if p.get("settled")]
    if len(settled) < 3:
        return {
            "sharpe_like": None,
            "sortino_like": None,
            "stddev_profit_per_pick": None,
            "downside_stddev": None,
            "equity_vol": {},
        }
    contribs = [_profit_contribution(p) for p in settled]
    mean_profit = mean(contribs)
    variance = pstdev(contribs) if len(contribs) > 1 else 0.0
    sharpe = mean_profit / variance if variance > 0 else None
    negatives = [c for c in contribs if c < 0]
    if negatives:
        downside_std = math.sqrt(sum(c * c for c in negatives) / len(contribs))
    else:
        downside_std = 0.0
    sortino = mean_profit / downside_std if downside_std > 0 else None
    return {
        "sharpe_like": round(sharpe, 6) if sharpe is not None else None,
        "sortino_like": round(sortino, 6) if sortino is not None else None,
        "stddev_profit_per_pick": round(variance, 6) if variance else 0.0,
        "downside_stddev": round(downside_std, 6),
        "equity_vol": {},
    }


# -------------------- Latency metrics --------------------
def _latency_metrics(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_latency_metrics:
        return {}
    durations: List[float] = []
    for p in ledger:
        if p.get("settled"):
            c = _parse_dt(p.get("created_at"))
            se = _parse_dt(p.get("settled_at"))
            if c and se:
                durations.append((se - c).total_seconds())
    if not durations:
        return {"avg_settlement_latency_sec": None}
    return {"avg_settlement_latency_sec": round(sum(durations) / len(durations), 2)}


# -------------------- League breakdown --------------------
def _league_breakdown(ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_league_breakdown:
        return []
    by_league: Dict[Any, List[Dict[str, Any]]] = {}
    for p in ledger:
        lg = p.get("league_id")
        if lg is None:
            continue
        by_league.setdefault(lg, []).append(p)
    rows: List[Dict[str, Any]] = []
    for lg, picks in by_league.items():
        stats = _compute_profit_and_stats(picks)
        rows.append({
            "league_id": lg,
            "picks": stats["picks"],
            "settled": stats["settled"],
            "profit_units": stats["profit_units"],
            "yield": stats["yield"],
            "hit_rate": stats["hit_rate"],
        })
    rows.sort(key=lambda r: r["picks"], reverse=True)
    return rows[: s.roi_league_max]


# -------------------- Time buckets --------------------
def _time_buckets(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_time_buckets:
        return {}
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "h00_05": [],
        "h06_11": [],
        "h12_17": [],
        "h18_23": [],
    }
    for p in ledger:
        c = _parse_dt(p.get("created_at"))
        if not c:
            continue
        h = c.hour
        if 0 <= h <= 5:
            buckets["h00_05"].append(p)
        elif 6 <= h <= 11:
            buckets["h06_11"].append(p)
        elif 12 <= h <= 17:
            buckets["h12_17"].append(p)
        else:
            buckets["h18_23"].append(p)
    out: Dict[str, Any] = {}
    for k, arr in buckets.items():
        if arr:
            out[k] = _compute_profit_and_stats(arr)
        else:
            out[k] = {"picks": 0, "settled": 0, "profit_units": 0.0, "yield": 0.0, "hit_rate": 0.0}
    return out


# -------------------- Edge buckets --------------------
def _edge_buckets(ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.roi_edge_buckets:
        return []
    settled = [p for p in ledger if p.get("settled") and isinstance(p.get("edge"), (int, float))]
    if not settled:
        return []
    results: List[Dict[str, Any]] = []
    for spec in s.roi_edge_buckets:
        spec = spec.strip()
        if not spec or "-" not in spec:
            continue
        left, right = spec.split("-", 1)
        left_v = float(left) if left else None
        right_v = float(right) if right else None

        def match(edge: float) -> bool:
            if left_v is not None and edge < left_v:
                return False
            if right_v is not None and edge >= right_v:
                return False
            return True

        picks = [p for p in settled if match(float(p["edge"]))]
        if not picks:
            results.append({
                "range": spec,
                "picks": 0,
                "settled": 0,
                "profit_units": 0.0,
                "yield": 0.0,
                "hit_rate": 0.0
            })
            continue
        stats = _compute_profit_and_stats(picks)
        results.append({
            "range": spec,
            "picks": stats["picks"],
            "settled": stats["settled"],
            "profit_units": stats["profit_units"],
            "yield": stats["yield"],
            "hit_rate": stats["hit_rate"],
        })
    return results


# -------------------- Profit normalizations --------------------
def _profit_normalizations(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [p for p in ledger if p.get("settled")]
    if not settled:
        return {"profit_per_pick": 0.0, "profit_per_unit_staked": 0.0}
    total_profit = sum(_profit_contribution(p) for p in settled)
    total_stake = sum(float(p.get("stake", 1.0)) for p in settled)
    return {
        "profit_per_pick": round(total_profit / len(settled), 6),
        "profit_per_unit_staked": round(total_profit / total_stake, 6) if total_stake > 0 else 0.0,
    }


# -------------------- Odds / Kelly helpers --------------------
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
    return (
        round(stake, 6),
        round(fraction, 6),
        round(fraction_capped, 6),
        model_prob,
        b,
    )


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


def _build_snapshot(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_odds_snapshot:
        return None
    market = entry.get("market")
    if not isinstance(market, dict):
        return None
    base_outcomes: Dict[str, float] = {}
    for k in ("home_win", "draw", "away_win"):
        v = market.get(k)
        if isinstance(v, (int, float)) and v > 1.01:
            base_outcomes[k] = float(v)
    if not base_outcomes:
        return None
    implied_raw = {k: 1.0 / v for k, v in base_outcomes.items()}
    s_sum = sum(implied_raw.values())
    implied_norm = {k: round(v / s_sum, 6) for k, v in implied_raw.items()} if s_sum > 0 else {}
    overround = round(s_sum - 1.0, 6) if s_sum > 0 else 0.0
    provider = (
        entry.get("source")
        or entry.get("provider")
        or s.odds_default_source
    )
    return {
        "market_snapshot": base_outcomes,
        "snapshot_implied": implied_norm,
        "snapshot_overround": overround,
        "snapshot_provider": provider,
        "snapshot_at": _now_iso(),
    }


def _append_timeline(base: Path, metrics: Dict[str, Any]) -> None:
    s = get_settings()
    if not s.enable_roi_timeline:
        return
    history_path = base / s.roi_timeline_file
    daily_path = base / s.roi_daily_file
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
    except Exception as exc:
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
    except Exception as exc:
        logger.error("Errore salvataggio daily ROI: %s", exc)


# -------------------- Batch 37 NEW analytics helpers --------------------
def _equity_curve_settled(ledger: List[Dict[str, Any]]) -> List[float]:
    eq = []
    running = 0.0
    settled = [p for p in ledger if p.get("settled")]
    settled.sort(key=lambda x: x.get("created_at") or "")
    for p in settled:
        running += _profit_contribution(p)
        eq.append(running)
    return eq


def _equity_volatility(equity: List[float], windows: List[int]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not equity:
        return out
    increments = [equity[i] - equity[i - 1] for i in range(1, len(equity))]
    if not increments:
        return out
    for w in windows:
        slice_inc = increments[-w:] if len(increments) > w else increments
        if len(slice_inc) > 1:
            m = sum(slice_inc) / len(slice_inc)
            var = sum((x - m) ** 2 for x in slice_inc) / len(slice_inc)
            out[f"w{w}"] = round(math.sqrt(var), 6)
        else:
            out[f"w{w}"] = 0.0
    return out


def _profit_distribution(contribs: List[float]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_profit_distribution or not contribs:
        return {}
    arr = sorted(contribs)

    def pct(p: float) -> float:
        k = int(round(p * (len(arr) - 1)))
        return arr[k]

    p10 = pct(0.10)
    p25 = pct(0.25)
    p50 = pct(0.50)
    p75 = pct(0.75)
    p90 = pct(0.90)
    if len(arr) > 1:
        m = sum(arr)/len(arr)
        var = sum((x-m)**2 for x in arr)/len(arr)
        std = math.sqrt(var) if var > 0 else 0.0
        skew_proxy = (m - p50)/std if std > 0 else 0.0
    else:
        skew_proxy = 0.0
    return {
        "p10": round(p10, 6),
        "p25": round(p25, 6),
        "median": round(p50, 6),
        "p75": round(p75, 6),
        "p90": round(p90, 6),
        "skew_proxy": round(skew_proxy, 6),
    }


def _risk_of_ruin_approx(ledger: List[Dict[str, Any]]) -> Optional[float]:
    s = get_settings()
    if not s.enable_roi_ror:
        return None
    settled = [p for p in ledger if p.get("settled")]
    if len(settled) < 30:
        return None
    wins = [p for p in settled if p.get("result") == "win"]
    win_rate = len(wins)/len(settled) if settled else 0.0
    if win_rate <= 0 or win_rate >= 1:
        return None
    win_profits = []
    for p in wins:
        stake = float(p.get("stake", 1.0))
        payout = float(p.get("payout", 0.0))
        win_profits.append(payout - stake)
    avg_win = sum(win_profits)/len(win_profits) if win_profits else 0.0
    if avg_win <= 0:
        return None
    avg_stake = sum(float(p.get("stake", 1.0)) for p in settled)/len(settled)
    edge = (avg_win * win_rate) - (1 - win_rate)
    if edge <= 0:
        return 1.0
    capital_units = 50.0
    ratio = edge / avg_win if avg_win > 0 else 0.0
    base = max(0.01, 1 - ratio)
    approx = base ** (capital_units / max(0.1, avg_stake))
    return round(min(max(approx, 0.0), 1.0), 6)


def _compute_source_efficiency(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_source_efficiency:
        return {}
    out: Dict[str, Any] = {}
    for src in ("prediction", "consensus", "merged"):
        picks = [p for p in ledger if p.get("source") == src and p.get("settled")]
        if not picks:
            continue
        contribs = [_profit_contribution(p) for p in picks]
        if not contribs:
            continue
        avg = sum(contribs)/len(contribs)
        if len(contribs) > 1:
            m = avg
            var = sum((x-m)**2 for x in contribs)/len(contribs)
            std = math.sqrt(var) if var > 0 else 0.0
        else:
            std = 0.0
        eff = avg/std if std > 0 else None
        out[src] = {
            "eff_index": round(eff, 6) if eff is not None else None,
            "avg_profit_per_pick": round(avg, 6),
            "stddev_profit_per_pick": round(std, 6),
            "settled": len(picks),
        }
    return out


def _edge_clv_corr(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_edge_clv_corr:
        return {}
    pairs = [
        (float(p.get("edge")), float(p.get("clv_pct")))
        for p in ledger
        if p.get("settled") and isinstance(p.get("edge"), (int, float)) and isinstance(p.get("clv_pct"), (int, float))
    ]
    if len(pairs) < 10:
        return {"pearson_r": None, "n": len(pairs)}
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    mx = sum(xs)/len(xs)
    my = sum(ys)/len(ys)
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x-mx)**2 for x in xs))
    deny = math.sqrt(sum((y-my)**2 for y in ys))
    if denx <= 0 or deny <= 0:
        r = None
    else:
        r = num/(denx*deny)
    return {"pearson_r": round(r, 6) if r is not None else None, "n": len(pairs)}


def _aging_buckets_stats(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_aging_buckets:
        return {}
    settled = [p for p in ledger if p.get("settled")]
    if not settled:
        return {}
    data: Dict[int, int] = {}
    for p in settled:
        c = _parse_dt(p.get("created_at"))
        se = _parse_dt(p.get("settled_at"))
        if not c or not se:
            continue
        delta_days = int((se - c).total_seconds() // 86400)
        data[delta_days] = data.get(delta_days, 0) + 1
    total = sum(data.values())
    out: Dict[str, Any] = {}
    for bucket in s.roi_aging_buckets:
        cum = sum(v for d, v in data.items() if d <= bucket)
        out[str(bucket)] = {"picks": cum, "pct": round(cum/total, 6) if total>0 else 0.0}
    return out


def _side_breakdown(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_side_breakdown:
        return {}
    sides: Dict[str, List[Dict[str, Any]]] = {"home_win": [], "draw": [], "away_win": []}
    for p in ledger:
        side = p.get("side")
        if side in sides:
            sides[side].append(p)
    out: Dict[str, Any] = {}
    for side, arr in sides.items():
        if arr:
            out[side] = _compute_profit_and_stats(arr)
        else:
            out[side] = {"picks": 0, "settled": 0, "profit_units": 0.0, "yield": 0.0, "hit_rate": 0.0}
    return out


def _parse_numeric_range(spec: str) -> tuple[Optional[float], Optional[float]]:
    """
    Parsing robusto di range numerici con estremi opzionali e segni:
      "-0.1--0.05"  -> (-0.1, -0.05)
      "-0.05-0"     -> (-0.05, 0.0)
      "0-0.05"      -> (0.0, 0.05)
      "0.05-0.1"    -> (0.05, 0.1)
      "0.1-"        -> (0.1, None)
      "-0.1-"       -> (-0.1, None)
    In caso di formato non valido ritorna (None, None).
    """
    spec = spec.strip()
    if not spec:
        return (None, None)
    m = re.match(r'^\s*([+-]?\d+(?:\.\d+)?)?\s*-\s*([+-]?\d+(?:\.\d+)?)?\s*$', spec)
    if not m:
        return (None, None)
    left_s, right_s = m.group(1), m.group(2)
    try:
        left_v = float(left_s) if left_s is not None else None
    except ValueError:
        left_v = None
    try:
        right_v = float(right_s) if right_s is not None else None
    except ValueError:
        right_v = None
    return (left_v, right_v)


def _clv_buckets_distribution(ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_clv_buckets:
        return []
    settled = [
        p for p in ledger
        if p.get("settled") and isinstance(p.get("clv_pct"), (int, float))
    ]
    if not settled:
        return []
    out: List[Dict[str, Any]] = []
    for spec in s.roi_clv_buckets:
        spec = spec.strip()
        if not spec or "-" not in spec:
            continue
        left_v, right_v = _parse_numeric_range(spec)
        if left_v is None and right_v is None:
            continue

        def match(v: float) -> bool:
            if left_v is not None and v < left_v:
                return False
            if right_v is not None and v >= right_v:
                return False
            return True

        picks = [p for p in settled if match(float(p["clv_pct"]))]
        if not picks:
            out.append({
                "range": spec,
                "picks": 0,
                "profit_units": 0.0,
                "yield": 0.0
            })
            continue
        stats = _compute_profit_and_stats(picks)
        out.append({
            "range": spec,
            "picks": stats["picks"],
            "profit_units": stats["profit_units"],
            "yield": stats["yield"],
        })
    return out


def _stake_advisory(metrics: Dict[str, Any]) -> Dict[str, Any]:
    s = get_settings()
    if not s.enable_roi_stake_advisory:
        return {}
    peak = metrics.get("peak_profit") or 0.0
    curr_dd = metrics.get("current_drawdown") or 0.0
    dd_pct = (curr_dd/peak) if peak>0 else 0.0
    if dd_pct >= s.roi_stake_advisory_dd_pct:
        return {
            "recommended_factor": 0.7,
            "reason": "deep_drawdown",
            "dd_pct": round(dd_pct, 4),
        }
    return {}


def _enhance_deciles(deciles: List[Dict[str, Any]], ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not deciles:
        return deciles
    settled = [p for p in ledger if p.get("settled") and isinstance(p.get("edge"), (int, float))]
    for d in deciles:
        emin = d.get("edge_min")
        emax = d.get("edge_max")
        bucket_picks = [
            p for p in settled
            if emin is not None and emax is not None and emin <= p["edge"] <= emax
        ]
        stats = _compute_profit_and_stats(bucket_picks) if bucket_picks else None
        d["hit_rate"] = stats["hit_rate"] if stats else 0.0
        d["yield"] = stats["yield"] if stats else 0.0
    return deciles


def _hit_rate_multi(rolling_multi: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in rolling_multi.items():
        if isinstance(v, dict) and "hit_rate" in v:
            out[k] = v["hit_rate"]
    return out


def _anomaly_flags(metrics: Dict[str, Any]) -> Dict[str, bool]:
    s = get_settings()
    if not s.enable_roi_anomaly_flags:
        return {}
    dd_alert = False
    yd_alert = False
    vol_alert = False
    peak = metrics.get("peak_profit") or 0.0
    curr_dd = metrics.get("current_drawdown") or 0.0
    if peak > 0 and curr_dd / peak >= s.roi_anomaly_dd_threshold:
        dd_alert = True
    y_total = metrics.get("yield") or 0.0
    y_rolling = metrics.get("yield_rolling") or 0.0
    if y_total > 0 and (y_total - y_rolling) / y_total >= s.roi_anomaly_yield_drop:
        yd_alert = True
    equity_vol = metrics.get("risk", {}).get("equity_vol", {})
    if equity_vol:
        vals = list(equity_vol.values())
        if vals:
            sorted_v = sorted(vals)
            mid = sorted_v[len(sorted_v)//2]
            last_key = max(equity_vol.keys(), key=lambda k: int(k[1:]) if k.startswith("w") else 0)
            last_val = equity_vol.get(last_key) or 0.0
            if mid > 0 and last_val / mid >= s.roi_anomaly_vol_mult:
                vol_alert = True
    return {
        "drawdown_alert": dd_alert,
        "yield_drop_alert": yd_alert,
        "vol_spike_alert": vol_alert,
    }


def _export_schema_if_enabled(base: Path, metrics: Dict[str, Any]) -> None:
    s = get_settings()
    if not s.enable_roi_schema_export:
        return
    schema = {
        "schema_version": "1.0",
        "description": "ROI metrics schema (core+plus batch37)",
        "top_level_keys": sorted(list(metrics.keys())),
    }
    try:
        _save_json_atomic(base / "roi_metrics.schema.json", schema)
    except Exception as exc:
        logger.error("schema_export_failed %s", exc)


# -------------------- Pruning / Archive --------------------
def _prune_ledger(base: Path, ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = get_settings()
    if s.roi_ledger_max_picks <= 0 and s.roi_ledger_max_age_days <= 0:
        return ledger
    archive_enabled = s.enable_roi_ledger_archive
    archive = load_ledger_archive(base) if archive_enabled else []
    ledger.sort(key=lambda p: p.get("created_at") or "")
    original_len = len(ledger)

    # Age pruning
    if s.roi_ledger_max_age_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=s.roi_ledger_max_age_days)
        kept = []
        removed = []
        for p in ledger:
            c = _parse_dt(p.get("created_at"))
            if c and c < cutoff:
                removed.append(p)
            else:
                kept.append(p)
        ledger = kept
        if archive_enabled and removed:
            archive.extend(removed)

    # Count pruning
    if s.roi_ledger_max_picks > 0 and len(ledger) > s.roi_ledger_max_picks:
        overflow = len(ledger) - s.roi_ledger_max_picks
        removed = ledger[:overflow]
        ledger = ledger[overflow:]
        if archive_enabled and removed:
            archive.extend(removed)

    if archive_enabled and archive:
        save_ledger_archive(base, archive)
    if len(ledger) != original_len:
        logger.info(
            "ledger_pruned",
            extra={"before": original_len, "after": len(ledger), "archived": len(archive) if archive_enabled else 0},
        )
    return ledger


# -------------------- Metrics assembly --------------------
def compute_metrics(ledger: List[Dict[str, Any]]) -> Dict[str, Any]:
    global_stats = _compute_profit_and_stats(ledger)

    pred_picks = [p for p in ledger if p.get("source") == "prediction"]
    cons_picks = [p for p in ledger if p.get("source") == "consensus"]
    merged_picks = [p for p in ledger if p.get("source") == "merged"]

    pred_stats = _compute_profit_and_stats(pred_picks)
    cons_stats = _compute_profit_and_stats(cons_picks)
    merged_stats = _compute_profit_and_stats(merged_picks)

    legacy_roll = _legacy_single_rolling(ledger)
    rolling_multi = _rolling_window_stats_multi(ledger)
    eq = _equity_stats(ledger)
    streaks = _streak_stats(ledger)
    clv_base = _clv_aggregate(ledger)
    clv_block = _finalize_clv_block(clv_base, global_stats["yield"]) if clv_base else {}
    risk = _risk_metrics(ledger)
    stake_bd = _stake_breakdown(ledger)
    source_bd = _source_breakdown(ledger)
    latency = _latency_metrics(ledger)
    deciles = _edge_deciles(ledger)
    deciles = _enhance_deciles(deciles, ledger)
    league_bd = _league_breakdown(ledger)
    time_bd = _time_buckets(ledger)
    edge_buckets = _edge_buckets(ledger)
    profit_norm = _profit_normalizations(ledger)

    # Batch 37 additions
    equity_curve = _equity_curve_settled(ledger)
    s = get_settings()
    equity_vol = {}
    if s.enable_roi_equity_vol:
        equity_vol = _equity_volatility(equity_curve, s.roi_equity_vol_windows)
    if "equity_vol" in risk and isinstance(risk["equity_vol"], dict):
        risk["equity_vol"].update(equity_vol)
    else:
        risk["equity_vol"] = equity_vol

    contribs_all = [_profit_contribution(p) for p in ledger if p.get("settled")]
    profit_distribution = _profit_distribution(contribs_all)
    risk_of_ruin = _risk_of_ruin_approx(ledger)
    source_eff = _compute_source_efficiency(ledger)
    edge_clv_corr = _edge_clv_corr(ledger)
    aging_b = _aging_buckets_stats(ledger)
    side_bd = _side_breakdown(ledger)
    clv_buckets = _clv_buckets_distribution(ledger)
    hit_rate_multi = _hit_rate_multi(rolling_multi)

    metrics = {
        "generated_at": _now_iso(),
        "total_picks": global_stats["picks"],
        "settled_picks": global_stats["settled"],
        "open_picks": global_stats["open"],
        "wins": global_stats["wins"],
        "losses": global_stats["losses"],
        "profit_units": global_stats["profit_units"],
        "yield": global_stats["yield"],
        "hit_rate": global_stats["hit_rate"],

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

        "picks_merged": merged_stats["picks"],
        "settled_merged": merged_stats["settled"],
        "open_merged": merged_stats["open"],
        "wins_merged": merged_stats["wins"],
        "losses_merged": merged_stats["losses"],
        "profit_units_merged": merged_stats["profit_units"],
        "yield_merged": merged_stats["yield"],
        "hit_rate_merged": merged_stats["hit_rate"],

        "peak_profit": eq["peak_profit"],
        "max_drawdown": eq["max_drawdown"],
        "max_drawdown_pct": eq["max_drawdown_pct"],
        "current_drawdown": eq["current_drawdown"],
        "current_drawdown_pct": eq["current_drawdown_pct"],
        "equity_points": eq["equity_points"],
        "current_win_streak": streaks["current_win_streak"],
        "current_loss_streak": streaks["current_loss_streak"],
        "longest_win_streak": streaks["longest_win_streak"],
        "longest_loss_streak": streaks["longest_loss_streak"],

        "rolling_window_size": legacy_roll["rolling_window_size"],
        "picks_rolling": legacy_roll["picks_rolling"],
        "settled_rolling": legacy_roll["settled_rolling"],
        "profit_units_rolling": legacy_roll["profit_units_rolling"],
        "yield_rolling": legacy_roll["yield_rolling"],
        "hit_rate_rolling": legacy_roll["hit_rate_rolling"],
        "peak_profit_rolling": legacy_roll["peak_profit_rolling"],
        "max_drawdown_rolling": legacy_roll["max_drawdown_rolling"],

        "rolling_multi": rolling_multi,
        "clv": clv_block,
        "risk": risk,
        "stake_breakdown": stake_bd,
        "source_breakdown": source_bd,
        "latency": latency,
        "edge_deciles": deciles,
        "league_breakdown": league_bd,
        "time_buckets": time_bd,
        "edge_buckets": edge_buckets,
        "profit_per_pick": profit_norm["profit_per_pick"],
        "profit_per_unit_staked": profit_norm["profit_per_unit_staked"],

        "avg_clv_pct": clv_block.get("avg_clv_pct"),
        "median_clv_pct": clv_block.get("median_clv_pct"),
        "clv_positive_rate": clv_block.get("clv_positive_rate"),
        "clv_realized_edge": clv_block.get("clv_realized_edge"),
        "realized_clv_win_avg": clv_block.get("realized_clv_win_avg"),
        "realized_clv_loss_avg": clv_block.get("realized_clv_loss_avg"),
    }

    metrics["profit_distribution"] = profit_distribution
    metrics["risk_of_ruin_approx"] = risk_of_ruin
    metrics["source_efficiency"] = source_eff
    metrics["edge_clv_corr"] = edge_clv_corr
    metrics["aging_buckets"] = aging_b
    metrics["side_breakdown"] = side_bd
    metrics["clv_buckets"] = clv_buckets
    metrics["hit_rate_multi"] = hit_rate_multi

    stake_adv = _stake_advisory(metrics)
    metrics["stake_advisory"] = stake_adv

    anomalies = _anomaly_flags(metrics)
    metrics["anomalies"] = anomalies

    return metrics


def save_metrics(base: Path, metrics: Dict[str, Any]) -> None:
    _save_json_atomic(base / "roi_metrics.json", metrics)


# -------------------- Effective threshold read --------------------
def _read_effective_threshold() -> Optional[float]:
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    path = base / s.value_alerts_dir / "value_alerts.json"
    raw = _load_json(path)
    if not raw:
        return None
    return raw.get("effective_threshold")


# -------------------- CSV export --------------------
def _write_roi_csv_export(ledger: List[Dict[str, Any]], metrics: Dict[str, Any]) -> None:
    s = get_settings()
    if not s.enable_roi_csv_export:
        return
    base = Path(s.bet_data_dir or "data") / s.roi_dir
    base.mkdir(parents=True, exist_ok=True)
    target = base / s.roi_csv_file

    rows = ledger
    if not s.roi_csv_include_open:
        rows = [r for r in rows if r.get("settled")]

    sort_key = s.roi_csv_sort
    rows.sort(key=lambda r: (r.get(sort_key) or ""))

    if s.roi_csv_limit and s.roi_csv_limit > 0:
        rows = rows[-s.roi_csv_limit :]

    effective_threshold = _read_effective_threshold()

    rolling_multi = metrics.get("rolling_multi", {})
    w7 = rolling_multi.get("w7", {})
    w30 = rolling_multi.get("w30", {})
    w90 = rolling_multi.get("w90", {})

    clv_block = metrics.get("clv", {}) or {}
    risk_block = metrics.get("risk", {}) or {}
    latency_block = metrics.get("latency", {}) or {}
    anomalies = metrics.get("anomalies", {}) or {}
    src_eff = metrics.get("source_efficiency", {}) or {}
    stake_adv = metrics.get("stake_advisory", {}) or {}
    equity_vol_block = risk_block.get("equity_vol", {}) if isinstance(risk_block.get("equity_vol"), dict) else {}

    header = [
        "fixture_id",
        "source",
        "value_type",
        "side",
        "edge",
        "stake",
        "stake_strategy",
        "decimal_odds",
        "kelly_fraction",
        "kelly_fraction_capped",
        "kelly_prob",
        "kelly_b",
        "settled",
        "result",
        "payout",
        "created_at",
        "settled_at",
        "profit_contribution",
        "closing_decimal_odds",
        "clv_pct",
        "avg_clv_pct",
        "median_clv_pct",
        "clv_positive_rate",
        "clv_realized_edge",
        "current_win_streak",
        "current_loss_streak",
        "longest_win_streak",
        "longest_loss_streak",
        "dynamic_threshold",
        "rate_limit_cap",
        "profit_per_pick",
        "profit_per_unit_staked",
        "sharpe_like",
        "sortino_like",
        "w7_profit_units",
        "w30_profit_units",
        "w90_profit_units",
        "avg_settlement_latency_sec",
        "equity_vol_w30",
        "equity_vol_w100",
        "risk_of_ruin_approx",
        "drawdown_alert",
        "yield_drop_alert",
        "vol_spike_alert",
        "eff_index_prediction",
        "eff_index_consensus",
        "eff_index_merged",
        "stake_adv_factor",
    ]

    tmp = target.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for p in rows:
            settled = p.get("settled") is True
            stake = float(p.get("stake", 0.0))
            result = p.get("result")
            payout = float(p.get("payout", 0.0)) if settled else 0.0
            if settled:
                if result == "win":
                    profit_contribution = round(payout - stake, 6)
                elif result == "loss":
                    profit_contribution = round(-stake, 6)
                else:
                    profit_contribution = 0.0
            else:
                profit_contribution = 0.0
            writer.writerow(
                [
                    p.get("fixture_id"),
                    p.get("source"),
                    p.get("value_type"),
                    p.get("side"),
                    p.get("edge"),
                    p.get("stake"),
                    p.get("stake_strategy"),
                    p.get("decimal_odds"),
                    p.get("kelly_fraction"),
                    p.get("kelly_fraction_capped"),
                    p.get("kelly_prob"),
                    p.get("kelly_b"),
                    p.get("settled"),
                    p.get("result"),
                    p.get("payout"),
                    p.get("created_at"),
                    p.get("settled_at"),
                    profit_contribution,
                    p.get("closing_decimal_odds"),
                    p.get("clv_pct"),
                    clv_block.get("avg_clv_pct"),
                    clv_block.get("median_clv_pct"),
                    clv_block.get("clv_positive_rate"),
                    clv_block.get("clv_realized_edge"),
                    metrics.get("current_win_streak"),
                    metrics.get("current_loss_streak"),
                    metrics.get("longest_win_streak"),
                    metrics.get("longest_loss_streak"),
                    effective_threshold,
                    s.roi_max_new_picks_per_day,
                    metrics.get("profit_per_pick"),
                    metrics.get("profit_per_unit_staked"),
                    risk_block.get("sharpe_like"),
                    risk_block.get("sortino_like"),
                    w7.get("profit_units"),
                    w30.get("profit_units"),
                    w90.get("profit_units"),
                    latency_block.get("avg_settlement_latency_sec"),
                    equity_vol_block.get("w30"),
                    equity_vol_block.get("w100"),
                    metrics.get("risk_of_ruin_approx"),
                    anomalies.get("drawdown_alert"),
                    anomalies.get("yield_drop_alert"),
                    anomalies.get("vol_spike_alert"),
                    (src_eff.get("prediction") or {}).get("eff_index"),
                    (src_eff.get("consensus") or {}).get("eff_index"),
                    (src_eff.get("merged") or {}).get("eff_index"),
                    stake_adv.get("recommended_factor"),
                ]
            )
    os.replace(tmp, target)
    logger.info("roi_csv_export_written", extra={"rows": len(rows), "file": str(target)})


# -------------------- Build / Update main --------------------
def build_or_update_roi(fixtures: List[Dict[str, Any]]) -> None:
    s = get_settings()
    if not s.enable_roi_tracking:
        return

    base = Path(s.bet_data_dir or "data") / s.roi_dir
    base.mkdir(parents=True, exist_ok=True)

    ledger = load_ledger(base)
    ledger = _prune_ledger(base, ledger)
    ledger_index = {
        (p.get("fixture_id"), p.get("source")): p
        for p in ledger
        if p.get("fixture_id")
    }

    fixtures_map = load_fixtures_map(fixtures)
    alerts = load_value_alerts()

    if s.merged_dedup_enable:
        merged_pairs = {
            (a.get("fixture_id"), a.get("value_side"))
            for a in alerts
            if a.get("source") == "merged"
        }
        if merged_pairs:
            alerts = [
                a
                for a in alerts
                if not (
                    a.get("source") in {"prediction", "consensus"}
                    and (a.get("fixture_id"), a.get("value_side")) in merged_pairs
                )
            ]

    min_edge = s.roi_min_edge
    include_consensus = s.roi_include_consensus
    include_merged = s.roi_include_merged
    default_stake_units = s.roi_stake_units

    predictions_index = load_predictions_index()
    consensus_index = load_consensus_index()
    odds_latest_index = load_odds_latest_index()

    now_ts = _now_iso()
    today = now_ts[:10]
    daily_limit = s.roi_max_new_picks_per_day
    rate_limit_strict = s.roi_rate_limit_strict

    existing_today = sum(
        1
        for p in ledger
        if isinstance(p.get("created_at"), str) and p["created_at"][:10] == today
    )

    accepted_sources = {"prediction"}
    if include_consensus:
        accepted_sources.add("consensus")
    if include_merged:
        accepted_sources.add("merged")

    for alert in alerts:
        fid = alert.get("fixture_id")
        source = str(alert.get("source"))
        value_type = alert.get("value_type")
        if source not in accepted_sources:
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

        if daily_limit > 0 and existing_today >= daily_limit:
            if rate_limit_strict:
                logger.info("rate_limit_skip_pick", extra={
                    "fixture_id": fid,
                    "source": source,
                    "today_count": existing_today,
                    "limit": daily_limit,
                })
                continue
            else:
                logger.info("rate_limit_exceeded_but_not_strict", extra={
                    "today_count": existing_today,
                    "limit": daily_limit,
                })

        side = alert.get("value_side")
        if not isinstance(side, str):
            continue

        decimal_odds, odds_src = _find_decimal_odds(fid, side, odds_latest_index, predictions_index)
        fair_prob = round(1 / decimal_odds, 6) if decimal_odds > 0 else 0.5

        model_prob: Optional[float] = None
        if source == "prediction":
            pred = predictions_index.get(fid)
            if pred:
                model_prob = _extract_side_prob(pred, side, "prediction")
        elif source == "consensus":
            cons = consensus_index.get(fid)
            if cons:
                model_prob = _extract_side_prob(cons, side, "consensus")
        elif source == "merged":
            pred = predictions_index.get(fid)
            cons = consensus_index.get(fid)
            mp_pred = _extract_side_prob(pred, side, "prediction") if pred else None
            mp_cons = _extract_side_prob(cons, side, "consensus") if cons else None
            model_prob = mp_pred if mp_pred is not None else mp_cons

        stake = default_stake_units
        stake_strategy = "fixed"
        kelly_fraction = None
        kelly_fraction_capped = None
        kelly_prob = None
        kelly_b = None

        if s.enable_kelly_staking:
            (stake, k_f, k_fc, kelly_prob, kelly_b) = _compute_kelly_stake(
                decimal_odds=decimal_odds,
                model_prob=model_prob,
                base_units=s.kelly_base_units,
                max_units=s.kelly_max_units,
                fraction_cap=s.kelly_edge_cap,
            )
            kelly_fraction = k_f
            kelly_fraction_capped = k_fc
            if kelly_fraction is not None and kelly_fraction > 0:
                stake_strategy = "kelly"

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

        if fx and fx.get("league_id") is not None:
            pick["league_id"] = fx.get("league_id")

        if snapshot_block:
            pick.update(snapshot_block)

        ledger.append(pick)
        ledger_index[key] = pick
        existing_today += 1

    enable_clv = s.enable_clv_capture
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

        if enable_clv:
            closing_entry = odds_latest_index.get(fid)
            if closing_entry:
                market = closing_entry.get("market")
                if isinstance(market, dict):
                    closing_odds = market.get(side)
                    if isinstance(closing_odds, (int, float)) and closing_odds > 1.01:
                        p["closing_decimal_odds"] = round(float(closing_odds), 6)
                        try:
                            clv_pct = (float(closing_odds) - decimal_odds) / decimal_odds
                        except ZeroDivisionError:
                            clv_pct = 0.0
                        p["clv_pct"] = round(clv_pct, 6)

    save_ledger(base, ledger)
    metrics = compute_metrics(ledger)
    save_metrics(base, metrics)
    _append_timeline(base, metrics)
    _write_roi_csv_export(ledger, metrics)
    _export_schema_if_enabled(base, metrics)

    logger.info(
        "roi_updated",
        extra={"picks": metrics["total_picks"], "settled": metrics["settled_picks"], "profit": metrics["profit_units"]},
    )


# -------------------- Public load helpers --------------------
def load_roi_summary() -> Optional[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_tracking:
        return None
    base = Path(s.bet_data_dir or "data") / s.roi_dir
    metrics = _load_json(base / "roi_metrics.json")
    if not metrics:
        return None
    return metrics


def load_roi_ledger() -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_tracking:
        return []
    base = Path(s.bet_data_dir or "data") / s.roi_dir
    return load_ledger(base)


def load_roi_timeline_raw() -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.enable_roi_tracking or not s.enable_roi_timeline:
        return []
    base = Path(s.bet_data_dir or "data") / s.roi_dir
    path = base / s.roi_timeline_file
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
    s = get_settings()
    if not s.enable_roi_tracking or not s.enable_roi_timeline:
        return {}
    base = Path(s.bet_data_dir or "data") / s.roi_dir
    path = base / s.roi_daily_file
    data = _load_json(path)
    if isinstance(data, dict):
        return data
    return {}
