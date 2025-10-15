#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.config import load_config

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def key_of(item: Dict[str, Any]) -> str:
    fid = item.get("fixture_id") or item.get("fixture", {}).get("id")
    market = item.get("market") or item.get("market_code", "1X2")
    sel = item.get("selection") or item.get("outcome") or item.get("pick")
    return f"{fid}::{market}::{sel}"

def get_prob(item: Dict[str, Any]) -> float:
    for k in ["prob","pred_prob","predicted_prob","p"]:
        if k in item:
            try:
                return float(item[k])
            except Exception:
                pass
    probs = item.get("probs")
    sel = item.get("selection")
    if isinstance(probs, dict) and sel in probs:
        return float(probs[sel])
    raise KeyError("Probabilità non trovata nell'item")

def main():
    cfg = load_config()
    data_dir = Path(cfg.DATA_DIR)

    pred_path = data_dir / "latest_predictions.json"
    odds_path = data_dir / "odds_latest.json"
    if not pred_path.exists() or not odds_path.exists():
        print("[enrich] predictions o odds mancanti, niente da fare.")
        return

    preds = load_json(pred_path)
    items: List[Dict[str, Any]] = preds if isinstance(preds, list) else preds.get("items", preds.get("predictions", []))

    odds = load_json(odds_path)
    odds_items: List[Dict[str, Any]] = odds if isinstance(odds, list) else odds.get("items", odds)

    odds_map: Dict[str, float] = {}
    for oi in odds_items:
        try:
            k = key_of(oi)
            odds_map[k] = float(oi.get("odds") or oi.get("price") or oi.get("decimal"))
        except Exception:
            continue

    enriched: List[Dict[str, Any]] = []
    for it in items:
        out = dict(it)
        try:
            k = key_of(it)
            p = float(get_prob(it))
            o = float(odds_map.get(k, 0))
            if o > 0 and 0 <= p <= 1:
                edge = p * o - 1.0
                out["edge"] = edge
                out.setdefault("value", {})
                out["value"]["active"] = bool(edge >= cfg.EFFECTIVE_THRESHOLD)
                out["value"]["threshold"] = cfg.EFFECTIVE_THRESHOLD
        except Exception:
            pass
        enriched.append(out)

    # Sovrascrive il file predictions con campi arricchiti (oppure scrivere un file _enriched separato)
    save_json(pred_path, enriched)
    print(f"[enrich] predictions arricchite con odds/edge/value (items={len(enriched)})")

if __name__ == "__main__":
    main()
