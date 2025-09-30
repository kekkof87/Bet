from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("api.app")

app = FastAPI(title="Bet Data API", version="0.1.0")


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura JSON %s: %s", path, exc)
        return None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/fixtures")
def get_fixtures() -> List[Dict[str, Any]]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    latest = base / "fixtures_latest.json"
    data = _load_json(latest)
    if data is None:
        return []
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="fixtures_latest.json non valido")
    return data


@app.get("/delta")
def get_delta() -> Dict[str, Any]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    events = base / "events" / "last_delta.json"
    metrics = base / "metrics" / "last_run.json"
    delta = _load_json(events) or {}
    met = _load_json(metrics) or {}
    summary = met.get("summary", {})
    return {
        "delta": delta,
        "summary": summary,
    }


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    metrics = base / "metrics" / "last_run.json"
    data = _load_json(metrics) or {}
    return data


@app.get("/scoreboard")
def get_scoreboard() -> Dict[str, Any]:
    settings = get_settings()
    base = Path(settings.bet_data_dir or "data")
    sb = base / "scoreboard.json"
    data = _load_json(sb)
    if data is None:
        raise HTTPException(status_code=404, detail="scoreboard non disponibile")
    return data


# Avvio rapido: python -m api.app
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=False)
