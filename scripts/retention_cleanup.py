#!/usr/bin/env python3
import time
from pathlib import Path
from typing import List

from scripts.config import load_config

SAFE_KEEP = {
    "latest_predictions.json",
    "value_alerts.json",
    "odds_latest.json",
    "last_delta.json",
    "fixtures.json",
    "scoreboard.json",
    "roi_metrics.json",
    "roi_daily.json",
    "roi_history.jsonl",
    "ledger.jsonl",
}

TARGET_DIRS = [
    "data/odds",
    "data/predictions",
    "data/roi",
    "data/archives",
]

def main():
    cfg = load_config()
    now = time.time()
    cutoff_sec = cfg.RETENTION_DAYS * 86400
    removed: List[str] = []

    for d in TARGET_DIRS:
        p = Path(d)
        if not p.exists():
            continue
        for child in p.rglob("*"):
            if child.is_file():
                if child.name in SAFE_KEEP:
                    continue
                try:
                    age = now - child.stat().st_mtime
                    if age > cutoff_sec:
                        child.unlink(missing_ok=True)
                        removed.append(str(child))
                except Exception:
                    continue

    print(f"[retention] removed files: {len(removed)}")
    for r in removed[:20]:
        print(f" - {r}")
    if len(removed) > 20:
        print(f" ... (+{len(removed)-20} altri)")

if __name__ == "__main__":
    main()
