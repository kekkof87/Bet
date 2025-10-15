from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


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


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def main() -> None:
    # Non importiamo get_settings per evitare dipendenze da chiavi API non necessarie
    bet_data_dir = Path(os.getenv("BET_DATA_DIR", "data"))
    predictions_dir = os.getenv("PREDICTIONS_DIR", "predictions")
    value_alerts_dir = os.getenv("VALUE_ALERTS_DIR", "value_alerts")

    enable_value_alerts = os.getenv("ENABLE_VALUE_ALERTS", "1").strip().lower() in {"1", "true", "yes", "y", "on"}
    if not enable_value_alerts:
        print("Value alerts disabilitati (ENABLE_VALUE_ALERTS=0).")
        return

    pred_path = bet_data_dir / predictions_dir / "latest_predictions.json"
    out_dir = bet_data_dir / value_alerts_dir
    out_path = out_dir / "value_alerts.json"

    raw = _load_json(pred_path)
    if not raw or not isinstance(raw, dict):
        print(f"Predictions non trovate o non valide: {pred_path}")
        return
    preds = raw.get("predictions")
    if not isinstance(preds, list):
        print("Predictions vuote.")
        return

    threshold = _float_env("VALUE_ALERT_MIN_EDGE", 0.05)
    alerts: List[Dict[str, Any]] = []

    for p in preds:
        if not isinstance(p, dict):
            continue
        fid = p.get("fixture_id")
        if fid is None:
            continue
        v = p.get("value")
        sides = ["home_win", "draw", "away_win"]
        candidates: List[tuple[str, float]] = []
        if isinstance(v, dict):
            bs = v.get("best_side")
            be = v.get("value_edge")
            if isinstance(bs, str) and isinstance(be, (int, float)):
                candidates.append((bs, float(be)))
            for k in sides:
                ev = v.get(f"edge_{k}") or v.get(k)
                if isinstance(ev, (int, float)):
                    candidates.append((k, float(ev)))
        if not candidates:
            prob = p.get("prob_adjusted") or p.get("prob")
            odds_block = (p.get("odds") or {}).get("odds_implied") if isinstance(p.get("odds"), dict) else None
            if isinstance(prob, dict) and isinstance(odds_block, dict):
                for k in sides:
                    pr = prob.get(k)
                    im = odds_block.get(k)
                    if isinstance(pr, (int, float)) and isinstance(im, (int, float)):
                        candidates.append((k, float(pr - im)))
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
    print(f"Value alerts generate: {out_path} (count={len(alerts)}, threshold={threshold:.4f})")


if __name__ == "__main__":
    main()
