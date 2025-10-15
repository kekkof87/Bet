#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.config import load_config

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def should_keep_status(status: Optional[str], allowed: Optional[List[str]]) -> bool:
    if not allowed:
        return True
    s_up = (status or "").upper()
    return s_up in {x.strip().upper() for x in allowed}

def main():
    cfg = load_config()
    data_dir = Path(cfg.DATA_DIR)

    pred_path = data_dir / "latest_predictions.json"
    if not pred_path.exists():
        print("[alerts] predictions non trovate, esco.")
        return
    preds = load_json(pred_path)
    items: List[Dict[str, Any]] = preds if isinstance(preds, list) else preds.get("items", preds.get("predictions", []))

    allowed_status = None
    if cfg.ALERTS_FILTER_STATUS:
        allowed_status = [x for x in cfg.ALERTS_FILTER_STATUS.split(",") if x.strip()]

    alerts: List[Dict[str, Any]] = []
    for it in items:
        edge = float(it.get("edge", 0.0))
        is_active = bool(it.get("value", {}).get("active", edge >= cfg.EFFECTIVE_THRESHOLD))
        st = it.get("status") or it.get("fixture", {}).get("status")
        if is_active and edge >= cfg.EFFECTIVE_THRESHOLD and should_keep_status(st, allowed_status):
            alerts.append(it)

    out_file = data_dir / "value_alerts.json"
    save_json(out_file, alerts)
    print(f"[alerts] value_alerts scritto: {out_file} (items={len(alerts)})")

if __name__ == "__main__":
    main()
