import os
import asyncio
import time
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge

from .utils.file_io import load_json, load_jsonl, filter_by_status, filter_predictions

DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).resolve()

# Gauge per età file in secondi
FILE_AGE_GAUGE = Gauge(
    "file_age_seconds",
    "Age in seconds of important data files",
    labelnames=("file",),
)

WATCH_DEFAULTS = [
    "latest_predictions.json",
    "value_alerts.json",
    "odds_latest.json",
    "last_delta.json",
    "fixtures.json",
    "roi_metrics.json",
    "roi_daily.json",
    "roi_history.jsonl",
]

def get_watch_files() -> List[Path]:
    env = os.environ.get("FILES_TO_WATCH")
    if env:
        files = [Path(x.strip()) for x in env.split(",") if x.strip()]
    else:
        files = [Path(x) for x in WATCH_DEFAULTS]
    # Risolvi in DATA_DIR se path relativo
    resolved: List[Path] = []
    for p in files:
        if p.is_absolute():
            resolved.append(p)
        else:
            resolved.append(DATA_DIR / p)
    return resolved

def update_file_age_metrics():
    now = time.time()
    for p in get_watch_files():
        label = str(p.name)
        try:
            stat = p.stat()
            age = max(0.0, now - stat.st_mtime)
            FILE_AGE_GAUGE.labels(file=label).set(age)
        except FileNotFoundError:
            # Se il file manca, imposta età a NaN -> scegliamo un valore alto per evidenziare (es. 1e12)
            FILE_AGE_GAUGE.labels(file=label).set(float("nan"))

async def _file_age_refresher():
    # Aggiorna periodicamente le metriche di età dei file
    while True:
        try:
            update_file_age_metrics()
        except Exception:
            # Non bloccare il loop su errore
            pass
        await asyncio.sleep(30)

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
    # Primo aggiornamento immediato e task periodico
    update_file_age_metrics()
    asyncio.create_task(_file_age_refresher())

@app.get("/health")
def health():
    return {"status": "ok", "data_dir": str(DATA_DIR)}

@app.get("/predictions")
def get_predictions(
    min_edge: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    active_only: bool = False,
    status: Optional[List[str]] = Query(default=None, description="Filter by fixture status (e.g., NS, 1H, 2H, FT)"),
):
    # Default polishing: se lo status non è specificato, applichiamo status=NS
    effective_status: Optional[List[str]] = status if status else ["NS"]

    path = DATA_DIR / "latest_predictions.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="latest_predictions.json not found")
    data = load_json(path)
    items = data if isinstance(data, list) else data.get("predictions", data)
    items = filter_predictions(items, min_edge=min_edge, active_only=active_only, status=effective_status)
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
    # Polishing: usa fixtures.json se presente, altrimenti fallback a last_delta.added
    fixtures_path = DATA_DIR / "fixtures.json"
    if fixtures_path.exists():
        items = load_json(fixtures_path)
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
    else:
        delta_path = DATA_DIR / "last_delta.json"
        if not delta_path.exists():
            raise HTTPException(status_code=404, detail="fixtures.json or last_delta.json not found")
        data = load_json(delta_path)
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
