from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("core.metrics")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_metrics_snapshot(payload: Dict[str, Any]) -> Path:
    """
    Scrive un file JSON 'last_run.json' nel METRICS_DIR (configurato) se abilitato.
    Sovrascrive sempre. Ritorna il path (anche se disabilitato).
    """
    settings = get_settings()
    target_dir = Path(os.getenv("BET_DATA_DIR", "data")) / settings.metrics_dir
    target = target_dir / "last_run.json"
    if not settings.enable_metrics_file:
        return target
    _ensure_dir(target_dir)
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


def write_last_delta_event(delta_payload: Dict[str, Any]) -> Path:
    """
    Scrive un file JSON 'last_delta.json' nel EVENTS_DIR se abilitato.
    """
    settings = get_settings()
    target_dir = Path(os.getenv("BET_DATA_DIR", "data")) / settings.events_dir
    target = target_dir / "last_delta.json"
    if not settings.enable_events_file:
        return target
    _ensure_dir(target_dir)
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(delta_payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


__all__ = ["write_metrics_snapshot", "write_last_delta_event"]
