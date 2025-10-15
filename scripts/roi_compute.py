#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple  # removed: Optional

def parse_ledger_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

def parse_ledger_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data:
            return list(data["items"])
        return []

def parse_ledger_csv(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(row)
    return items

def coerce_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def coerce_ts(v: Any) -> datetime:
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    if isinstance(v, str):
        # supporta ISO 8601
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(tz=timezone.utc)

def normalize_bet(row: Dict[str, Any]) -> Dict[str, Any]:
    # Campi attesi: timestamp, stake, odds, result in {win,loss,void,push}
    ts = row.get("timestamp") or row.get("time") or row.get("date")
    dt = coerce_ts(ts)
    stake = coerce_float(row.get("stake", row.get("amount", 0)))
    odds = coerce_float(row.get("odds", row.get("price", 0)))
    result = str(row.get("result", "")).lower()
    # profit/payout opzionali
    payout = row.get("payout")
    profit = row.get("profit")
    if profit is None:
        if result == "win":
            profit = stake * (odds - 1.0)
        elif result == "loss":
            profit = -stake
        elif result in ("void", "push"):
            profit = 0.0
        else:
            # sconosciuto -> 0
            profit = 0.0
    profit = coerce_float(profit, 0.0)
    if payout is None:
        payout = stake + profit
    payout = coerce_float(payout, 0.0)

    return {
        "timestamp": dt.isoformat(),
        "date": dt.date().isoformat(),
        "stake": stake,
        "odds": odds,
        "result": result if result in ("win","loss","void","push") else "unknown",
        "profit": profit,
        "payout": payout,
        "fixture_id": row.get("fixture_id"),
        "market": row.get("market"),
        "selection": row.get("selection") or row.get("pick"),
        "bookmaker": row.get("bookmaker"),
    }

def load_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        raw = parse_ledger_jsonl(path)
    elif path.suffix == ".csv":
        raw = parse_ledger_csv(path)
    else:
        raw = parse_ledger_json(path)
    return [normalize_bet(x) for x in raw]

def compute_metrics(bets: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    total_bets = len(bets)
    wins = sum(1 for b in bets if b["result"] == "win")
    losses = sum(1 for b in bets if b["result"] == "loss")
    voids = sum(1 for b in bets if b["result"] == "void")
    pushes = sum(1 for b in bets if b["result"] == "push")
    st_sum = sum(b["stake"] for b in bets)
    profit_sum = sum(b["profit"] for b in bets)
    avg_odds = (sum(b["odds"] for b in bets) / total_bets) if total_bets > 0 else 0.0
    denom_hr = wins + losses
    hit_rate = (wins / denom_hr) if denom_hr > 0 else 0.0
    yld = (profit_sum / st_sum) if st_sum > 0 else 0.0

    now = datetime.now(tz=timezone.utc).isoformat()
    metrics = {
        "generated_at": now,
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "pushes": pushes,
        "stake_sum": st_sum,
        "profit_sum": profit_sum,
        "yield": yld,
        "hit_rate": hit_rate,
        "avg_odds": avg_odds,
    }

    # Aggregazione giornaliera
    by_day: Dict[str, Dict[str, Any]] = {}
    for b in bets:
        d = b["date"]
        g = by_day.setdefault(d, {"date": d, "bets": 0, "stake": 0.0, "profit": 0.0})
        g["bets"] += 1
        g["stake"] += b["stake"]
        g["profit"] += b["profit"]
    daily = []
    cum_profit = 0.0
    for day in sorted(by_day.keys()):
        g = by_day[day]
        stake = g["stake"]
        profit = g["profit"]
        roi = (profit / stake) if stake > 0 else 0.0
        cum_profit += profit
        daily.append({"date": day, "bets": g["bets"], "stake": stake, "profit": profit, "roi": roi, "cum_profit": cum_profit})
    return metrics, daily

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def append_history(path: Path, metrics: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(metrics, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser(description="Compute ROI metrics/daily/history from ledger")
    ap.add_argument("--ledger", default="data/ledger.jsonl", type=str)
    ap.add_argument("--out-metrics", default="data/roi_metrics.json", type=str)
    ap.add_argument("--out-daily", default="data/roi_daily.json", type=str)
    ap.add_argument("--out-history", default="data/roi_history.jsonl", type=str)
    ap.add_argument("--append-history", action="store_true", help="Append snapshot to roi_history.jsonl")
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    bets = load_ledger(ledger_path)
    metrics, daily = compute_metrics(bets)

    save_json(Path(args.out_metrics), metrics)
    save_json(Path(args.out_daily), daily)
    if args.append_history:
        append_history(Path(args.out_history), metrics)

    print(f"[roi] metrics written to {args.out_metrics}, daily to {args.out_daily}, append_history={bool(args.append_history)}")

if __name__ == "__main__":
    main()
