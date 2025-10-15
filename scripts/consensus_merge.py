#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Any

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_prob(item: Dict[str, Any]) -> float:
    # Tollerante a vari schemi
    for key in ["prob", "pred_prob", "predicted_prob", "p"]:
        if key in item:
            try:
                return float(item[key])
            except Exception:
                pass
    # es: {"probs":{"home":0.4,"draw":0.3,"away":0.3}} + selection
    probs = item.get("probs")
    sel = item.get("selection")
    if isinstance(probs, dict) and sel in probs:
        return float(probs[sel])
    raise KeyError("Probabilità non trovata nell'item")

def key_of(item: Dict[str, Any]) -> str:
    fid = item.get("fixture_id") or item.get("fixture", {}).get("id")
    market = item.get("market") or item.get("market_code", "1X2")
    sel = item.get("selection") or item.get("outcome") or item.get("pick")
    return f"{fid}::{market}::{sel}"

def weighted_avg(values: List[float], weights: List[float]) -> float:
    if not values:
        return math.nan
    if not weights or len(weights) != len(values):
        return sum(values) / len(values)
    s = sum(w * v for v, w in zip(values, weights))
    return s / max(1e-12, sum(weights))

def build_weights_map(cfg: Dict[str, Any]) -> Dict[str, float]:
    # config schema semplice: {"sources":{"modelA":1.0,"modelB":0.8}}
    sources = cfg.get("sources", {}) if cfg else {}
    return {str(k): float(v) for k, v in sources.items()}

def main():
    ap = argparse.ArgumentParser(description="Consensus/Merge predictions")
    ap.add_argument("--sources-dir", default="data/predictions/sources", type=str)
    ap.add_argument("--odds-file", default="data/odds_latest.json", type=str)
    ap.add_argument("--out", default="data/latest_predictions.json", type=str)
    ap.add_argument("--weights", default="consensus/config.yml", type=str)
    ap.add_argument("--min-models", default=1, type=int)
    args = ap.parse_args()

    src_dir = Path(args.sources_dir)
    files = sorted(src_dir.glob("*.json"))
    if not files:
        print(f"Nessun file sorgente in {src_dir}, esco senza modifiche.")
        return

    # Carica pesi (YAML opzionale)
    weights_map: Dict[str, float] = {}
    ypath = Path(args.weights)
    if ypath.exists():
        try:
            import yaml  # type: ignore
            with ypath.open("r", encoding="utf-8") as f:
                weights_map = build_weights_map(yaml.safe_load(f))
        except Exception:
            pass

    buckets: Dict[str, Dict[str, Any]] = {}
    for f in files:
        name = f.stem
        try:
            data = load_json(f)
            items = data if isinstance(data, list) else data.get("items", data.get("predictions", []))
            for it in items:
                k = key_of(it)
                entry = buckets.setdefault(k, {"samples": [], "meta": it})
                entry["samples"].append({"source": name, "prob": get_prob(it)})
        except Exception as e:
            print(f"Errore su {f}: {e}")

    # Carica odds per edge
    odds_data = {}
    try:
        odds_json = load_json(Path(args.odds_file))
        odds_items = odds_json if isinstance(odds_json, list) else odds_json.get("items", odds_json)
        for oi in odds_items:
            fid = oi.get("fixture_id")
            market = oi.get("market") or oi.get("market_code", "1X2")
            sel = oi.get("selection") or oi.get("outcome") or oi.get("pick")
            if fid and sel:
                odds_data[f"{fid}::{market}::{sel}"] = float(oi.get("odds") or oi.get("price") or oi.get("decimal", 0))
    except Exception:
        pass

    result: List[Dict[str, Any]] = []
    for k, v in buckets.items():
        samples = v["samples"]
        if len(samples) < args.min_models:
            continue
        values = [s["prob"] for s in samples]
        w = [float(weights_map.get(s["source"], 1.0)) for s in samples]
        p = weighted_avg(values, w)
        meta = v["meta"]
        out = dict(meta)
        out["consensus"] = {
            "n_models": len(samples),
            "sources": [s["source"] for s in samples],
            "weights_used": {s["source"]: weights_map.get(s["source"], 1.0) for s in samples},
            "prob": p,
        }
        # calcolo edge se odds disponibili
        odds = odds_data.get(k)
        if odds and odds > 0 and 0 <= p <= 1:
            ev = p * odds
            edge = ev - 1.0
            out["edge"] = edge
            out.setdefault("value", {})
            out["value"]["active"] = out["value"].get("active", True)
        result.append(out)

    save_json(Path(args.out), result)
    print(f"Consensus scritto in {args.out} (items={len(result)})")

if __name__ == "__main__":
    main()
