from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.config import get_settings
from core.logging import get_logger

log = get_logger("scripts.build_value_alerts")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> None:
    s = get_settings()
    if not s.enable_value_alerts:
        log.info("Value alerts disabilitati (ENABLE_VALUE_ALERTS=0).")
        return

    base = Path(s.bet_data_dir or "data")
    pred_path = base / s.predictions_dir / "latest_predictions.json"
    out_dir = base / s.value_alerts_dir
    out_path = out_dir / "value_alerts.json"

    raw = _load_json(pred_path)
    if not raw or not isinstance(raw, dict):
        log.info("Predictions non trovate o non valide: %s", pred_path)
        return
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        log.info("Predictions vuote.")
        return

    threshold = float(os.getenv("VALUE_ALERT_MIN_EDGE", s.value_alert_min_edge))
    alerts: List[Dict[str, Any]] = []

    for p in preds:
        if not isinstance(p, dict):
            continue
        fid = p.get("fixture_id")
        if fid is None:
            continue
        v = p.get("value")
        # Ci aspettiamo una struttura con edge per lato oppure un best_side con edge
        # Strategia robusta:
        sides = ["home_win", "draw", "away_win"]
        candidates: List[tuple[str, float]] = []
        if isinstance(v, dict):
            # caso 1: best_side/value_edge
            bs = v.get("best_side")
            be = v.get("value_edge")
            if isinstance(bs, str) and isinstance(be, (int, float)):
                candidates.append((bs, float(be)))
            # caso 2: edges per lato
            for k in sides:
                ev = v.get(f"edge_{k}") or v.get(k)
                if isinstance(ev, (int, float)):
                    candidates.append((k, float(ev)))
        # se non abbiamo 'value', prova a derivare da prob vs odds_implied
        if not candidates:
            prob = p.get("prob_adjusted") or p.get("prob")
            odds_block = (p.get("odds") or {}).get("odds_implied")
            if isinstance(prob, dict) and isinstance(odds_block, dict):
                for k in sides:
                    pr = prob.get(k)
                    im = odds_block.get(k)
                    if isinstance(pr, (int, float)) and isinstance(im, (int, float)):
                        candidates.append((k, float(pr - im)))

        # filtra per soglia
        for side, edge in candidates:
            if edge >= threshold:
                alerts.append(
                    {
                        "fixture_id": fid,
                        "source": "prediction",
                        "value_type": "prob_vs_market",
                        "value_side": side,
                        "value_edge": round(edge, 6),
                    }
                )

    payload = {
        "generated_at": _now_iso(),
        "effective_threshold": threshold,
        "alerts": alerts,
    }
    _save_json_atomic(out_path, payload)
    log.info("Value alerts generate: %s (count=%d, threshold=%.4f)", out_path, len(alerts), threshold)


if __name__ == "__main__":
    main()
