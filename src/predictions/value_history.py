from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("predictions.value_history")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _daily_filename(base: Path) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return base / f"value_history_{day}.jsonl"


def _rolling_filename(base: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return base / f"value_history_{ts}.jsonl"


def _rotate_if_needed(base: Path, max_files: int) -> None:
    files = sorted(
        [p for p in base.glob("value_history_*.jsonl") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    excess = len(files) - max_files
    if excess > 0:
        for old in files[:excess]:
            try:
                old.unlink()
            except Exception:  # pragma: no cover
                pass


def append_value_history(alerts: List[Dict[str, Any]]) -> None:
    """
    Salva ogni alert come riga JSON (JSONL).
    """
    settings = get_settings()
    if not settings.enable_value_history:
        return
    if not alerts:
        return

    base = Path(settings.bet_data_dir or "data") / settings.value_history_dir
    base.mkdir(parents=True, exist_ok=True)

    # Scegli file
    if settings.value_history_mode == "rolling":
        target = _rolling_filename(base)
    else:
        target = _daily_filename(base)

    lines: List[str] = []
    ts = _now_iso()
    for a in alerts:
        try:
            rec = {
                "ts": ts,
                "fixture_id": a.get("fixture_id"),
                "source": a.get("source"),
                "value_type": a.get("value_type"),
                "value_side": a.get("value_side"),
                "value_edge": a.get("value_edge"),
            }
            if a.get("model_version"):
                rec["model_version"] = a.get("model_version")
            # add consensus weight if available in consensus value (not stored here by default)
            lines.append(json.dumps(rec, ensure_ascii=False))
        except Exception:
            continue

    if lines:
        with open(target, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")
        logger.info(
            "value_history_appended",
            extra={"file": str(target), "count": len(lines), "mode": settings.value_history_mode},
        )

    if settings.value_history_mode == "rolling":
        try:
            _rotate_if_needed(base, settings.value_history_max_files)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore rotazione value_history: %s", exc)
