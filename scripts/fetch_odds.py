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
    out_file = data_dir / "odds_latest.json"

    if cfg.ODDS_PROVIDER != "model" or not cfg.ENABLE_ODDS_INGESTION:
        print("[odds] ODDS_PROVIDER != model o ingestion disabilitata. Nessuna azione.")
        return

    pred_path = data_dir / "latest_predictions.json"
    if not pred_path.exists():
        print(f"[odds] {pred_path} non trovato. Esco.")
        return
    preds = load_json(pred_path)
    items = preds if isinstance(preds, list) else preds.get("items", preds.get("predictions", []))

    odds_items: List[Dict[str, Any]] = []
    for it in items:
        try:
            p = max(1e-6, min(1-1e-6, float(get_prob(it))))  # clamp
            fair_odds = 1.0 / p
            # Applica margine opzionale (riduce convenientemente le odds)
            margin = max(0.0, float(cfg.MODEL_ODDS_MARGIN))
            decimal = max(1.01, fair_odds * (1.0 - margin))
            odds_items.append({
                "fixture_id": it.get("fixture_id") or it.get("fixture", {}).get("id"),
                "market": it.get("market") or it.get("market_code", "1X2"),
                "selection": it.get("selection") or it.get("outcome") or it.get("pick"),
                "bookmaker": "model",
                "odds": round(decimal, 4),
            })
        except Exception as e:
            # ignora item malformati
            continue

    save_json(out_file, odds_items)
    print(f"[odds] Scritto {out_file} (items={len(odds_items)})")

if __name__ == "__main__":
    main()
