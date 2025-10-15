#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import urllib.request

from scripts.config import load_config

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def post_json(url: str, payload: Dict[str, Any], timeout: int = 10) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getcode()

def main():
    cfg = load_config()
    if not cfg.ALERT_DISPATCH_WEBHOOK:
        print("[dispatch] ALERT_DISPATCH_WEBHOOK non impostato, nessun invio.")
        return
    alerts_path = Path(cfg.DATA_DIR) / "value_alerts.json"
    if not alerts_path.exists():
        print("[dispatch] Nessun value_alerts.json trovato, esco.")
        return
    try:
        alerts = load_json(alerts_path)
        if isinstance(alerts, dict) and "items" in alerts:
            alerts = alerts["items"]
        if not isinstance(alerts, list):
            alerts = []
    except Exception:
        alerts = []

    if not alerts:
        print("[dispatch] Nessun alert da inviare.")
        return

    payload = {
        "type": "value_alerts",
        "count": len(alerts),
        "ts": int(time.time()),
        "items": alerts[:50],  # limita payload
    }
    try:
        code = post_json(cfg.ALERT_DISPATCH_WEBHOOK, payload)
        print(f"[dispatch] webhook risposta HTTP {code}, items={len(alerts)}")
    except Exception as e:
        print(f"[dispatch] errore invio webhook: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
