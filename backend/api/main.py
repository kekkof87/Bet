import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .utils.file_io import load_json, load_jsonl, filter_by_status, filter_predictions

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

app = FastAPI(title="Betting Data API", default_response_class=ORJSONResponse)

# CORS per GUI locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

@app.get("/health")
def health():
    return {"status": "ok", "data_dir": str(DATA_DIR)}

@app.get("/predictions")
def get_predictions(
    min_edge: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    active_only: bool = False,
    status: Optional[List[str]] = Query(default=None, description="Filter by fixture status (e.g., NS, 1H, 2H, FT)"),
):
    path = DATA_DIR / "latest_predictions.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="latest_predictions.json not found")
    data = load_json(path)
    items = data if isinstance(data, list) else data.get("predictions", data)
    items = filter_predictions(items, min_edge=min_edge, active_only=active_only, status=status)
    return {"count": len(items), "items": items}

@app.get("/odds")
def get_odds():
    path = DATA_DIR / "odds_latest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="odds_latest.json not found")
    return load_json(path)

@app.get("/alerts")
def get_alerts():
    path = DATA_DIR / "value_alerts.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="value_alerts.json not found")
    return load_json(path)

@app.get("/fixtures")
def get_fixtures(status: Optional[List[str]] = Query(default=None)):
    # In assenza di un fixtures.json dedicato, usiamo last_delta.added come snapshot fixtures del run
    path = DATA_DIR / "last_delta.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="last_delta.json not found")
    data = load_json(path)
    items = data.get("added", [])
    if status:
        items = filter_by_status(items, status)
    return {"count": len(items), "items": items}

@app.get("/roi/metrics")
def get_roi_metrics():
    path = DATA_DIR / "roi_metrics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="roi_metrics.json not found")
    return load_json(path)

@app.get("/roi/daily")
def get_roi_daily():
    path = DATA_DIR / "roi_daily.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="roi_daily.json not found")
    return load_json(path)

@app.get("/roi/history")
def get_roi_history():
    path = DATA_DIR / "roi_history.jsonl"
    if not path.exists():
        raise HTTPException(status_code=404, detail="roi_history.jsonl not found")
    lines = load_jsonl(path)
    return {"count": len(lines), "items": lines}

@app.get("/scoreboard")
def get_scoreboard():
    path = DATA_DIR / "scoreboard.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="scoreboard.json not found")
    return load_json(path)

@app.get("/delta")
def get_last_delta():
    path = DATA_DIR / "last_delta.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="last_delta.json not found")
    return load_json(path)
