from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from core.config import get_settings
from core.logging import get_logger

router = APIRouter(tags=["delta"])
logger = get_logger("api.routes.delta")


def _default_delta() -> Dict[str, Any]:
    return {
        "added": [],
        "removed": [],
        "modified": [],
        "change_breakdown": {
            "score_change": 0,
            "status_change": 0,
            "both": 0,
            "other": 0,
        },
        "summary": {
            "added": 0,
            "removed": 0,
            "modified": 0,
            "total_new": 0,
        },
    }


@router.get("/delta", summary="Ultimo delta")
def get_delta():
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    delta_path = base / settings.events_dir / "last_delta.json"
    metrics_path = base / settings.metrics_dir / "last_run.json"

    payload = _default_delta()

    if delta_path.exists():
        try:
            raw_delta = json.loads(delta_path.read_text(encoding="utf-8"))
            if isinstance(raw_delta, dict):
                payload["added"] = raw_delta.get("added", []) or []
                payload["removed"] = raw_delta.get("removed", []) or []
                payload["modified"] = raw_delta.get("modified", []) or []
                if isinstance(raw_delta.get("change_breakdown"), dict):
                    payload["change_breakdown"] = raw_delta["change_breakdown"]
        except Exception as exc:  # pragma: no cover
            logger.error("Errore lettura last_delta.json: %s", exc)

    if metrics_path.exists():
        try:
            raw_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            if isinstance(raw_metrics, dict):
                summary = raw_metrics.get("summary")
                if isinstance(summary, dict):
                    payload["summary"].update(summary)
        except Exception as exc:  # pragma: no cover
            logger.error("Errore lettura last_run.json: %s", exc)

    payload["counts"] = {
        "added": len(payload["added"]),
        "removed": len(payload["removed"]),
        "modified": len(payload["modified"]),
    }
    return payload
