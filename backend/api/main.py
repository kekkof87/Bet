import os
import asyncio
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

# Tolleranza: se la libreria Prometheus non è installata, non blocchiamo l'avvio
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore
except Exception:
    Instrumentator = None  # type: ignore

from prometheus_client import Gauge

# Utils locali
try:
    from .utils.file_io import load_json, load_jsonl, filter_by_status, filter_predictions  # type: ignore
except Exception:
    # Fallback minimo se i utils non fossero disponibili
    import json

    def load_json(p: Path):
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_jsonl(p: Path):
        out = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def filter_by_status(items: List[Dict[str, Any]], statuses: List[str]):
        sset = {s.upper() for s in statuses}
        out = []
        for it in items:
            st = str(it.get("status", "")).upper()
            if st in sset:
                out.append(it)
        return out

    def filter_predictions(items: List[Dict[str, Any]], min_edge: Optional[float], active_only: bool, status: Optional[List[str]]):
        # Pass-through minimale: filtra solo per edge e status
        out = items[:]
        if status:
            out = [it for it in out if str(it.get("status", "")).upper() in {s.upper() for s in status}]
        if min_edge is not None:
            def get_edge(x):
                e = x.get("edge")
                try:
                    return float(e)
                except Exception:
                    return -1.0
            out = [it for it in out if get_edge(it) >= float(min_edge)]
        return out

# dotenv set_key per /settings
try:
    from dotenv import set_key, find_dotenv
except Exception:
    set_key = None  # type: ignore
    find_dotenv = None  # type: ignore

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
            FILE_AGE_GAUGE.labels(file=label).set(float("nan"))

async def _file_age_refresher():
    while True:
        try:
            update_file_age_metrics()
        except Exception:
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

# Instrumentazione Prometheus
if Instrumentator:
    try:
        Instrumentator().instrument(app).expose(app, include_in_schema=False)
    except Exception as e:
        print(f"[metrics] Instrumentator init error: {e}")
else:
    print("[metrics] prometheus_fastapi_instrumentator non installato: /metrics disabilitato")

@app.on_event("startup")
async def _startup():
    # Primo aggiornamento e task periodico per file_age_seconds
    update_file_age_metrics()
    asyncio.create_task(_file_age_refresher())

@app.get("/health")
def health():
    return {"status": "ok", "data_dir": str(DATA_DIR)}

# ---------------------
# Endpoint esistenti
# ---------------------
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
    # Accettiamo sia {items:[...]} che {"predictions":[...]} che lista pura
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, dict) and "predictions" in data:
        items = data["predictions"]
    else:
        items = data
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

# ---------------------
# Nuovi helper server-side
# ---------------------
def _normalize_name(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch.isspace()).strip()

def _load_fixtures() -> List[Dict[str, Any]]:
    fixtures_path = DATA_DIR / "fixtures.json"
    if fixtures_path.exists():
        obj = load_json(fixtures_path)
        items = obj.get("items", obj) if isinstance(obj, dict) else obj
        return items if isinstance(items, list) else []
    delta_path = DATA_DIR / "last_delta.json"
    if delta_path.exists():
        obj = load_json(delta_path)
        return obj.get("added", [])
    return []

def _load_odds_by_fixture() -> Dict[str, Dict[str, Any]]:
    # Restituisce dizionario fixture_id -> record odds (best h2h se disponibile)
    odds_path = DATA_DIR / "odds_latest.json"
    if not odds_path.exists():
        return {}
    obj = load_json(odds_path)
    items = obj.get("items", obj) if isinstance(obj, dict) else obj
    out: Dict[str, Dict[str, Any]] = {}
    for it in items if isinstance(items, list) else []:
        fid = str(it.get("fixture_id") or it.get("fixture_key") or "")
        if not fid:
            continue
        out[fid] = it
    return out

def _load_predictions_index() -> Dict[str, Dict[str, Any]]:
    pred_path = DATA_DIR / "latest_predictions.json"
    if not pred_path.exists():
        return {}
    obj = load_json(pred_path)
    items = obj.get("items", obj.get("predictions", obj)) if isinstance(obj, dict) else obj
    idx: Dict[str, Dict[str, Any]] = {}
    for it in items if isinstance(items, list) else []:
        fid = str(it.get("fixture_id") or "")
        if fid:
            idx[fid] = it
    return idx

def _compute_value_picks(edge_min: float = 0.03) -> Dict[str, Any]:
    fixtures = _load_fixtures()
    odds_idx = _load_odds_by_fixture()
    preds_idx = _load_predictions_index()

    out_items: List[Dict[str, Any]] = []
    for fx in fixtures:
        fid = str(fx.get("fixture_id") or "")
        if not fid:
            continue
        pred = preds_idx.get(fid)
        odds = odds_idx.get(fid)
        if not pred or not odds:
            continue

        probs = pred.get("probabilities") or {}
        ph = float(probs.get("home") or 0.0)
        pd = float(probs.get("draw") or 0.0)
        pa = float(probs.get("away") or 0.0)

        best = odds.get("best", {})  # atteso: {"home": x, "draw": y, "away": z, "book": "..."}
        oh = float(best.get("home") or 0.0)
        od = float(best.get("draw") or 0.0)
        oa = float(best.get("away") or 0.0)

        picks: List[Tuple[str, float, float]] = [
            ("home", ph, oh),
            ("draw", pd, od),
            ("away", pa, oa),
        ]
        for sel, p, o in picks:
            if p <= 0.0 or o <= 1.0:
                continue
            fair = 1.0 / p
            edge = (o - fair) / fair
            if edge >= edge_min:
                out_items.append({
                    "fixture_id": fid,
                    "home": fx.get("home"),
                    "away": fx.get("away"),
                    "league": fx.get("league"),
                    "kickoff": fx.get("kickoff"),
                    "status": fx.get("status"),
                    "pick": sel,  # home/draw/away
                    "prob": p,
                    "fair_odds": fair,
                    "best_odds": o,
                    "edge": edge,
                    "book": best.get("book"),
                    "model": pred.get("model", "model"),
                })

    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": out_items}
    # scrive cache server-side
    try:
        (DATA_DIR / "value_picks.json").write_text(
            ORJSONResponse.render(out).decode("utf-8"), encoding="utf-8"
        )
    except Exception:
        pass
    return out

def _suggest_betslip(target_odds: float, min_picks: int = 2, max_picks: int = 8, edge_min: float = 0.03) -> Dict[str, Any]:
    vp = _compute_value_picks(edge_min=edge_min)["items"]
    # Ordina per probabilità decrescente
    vp_sorted = sorted(vp, key=lambda x: float(x.get("prob") or 0.0), reverse=True)

    def combine_until_target(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        acc = []
        prod = 1.0
        for it in items:
            o = float(it.get("best_odds") or 1.0)
            if o <= 1.0:
                continue
            if len(acc) < max_picks and prod * o <= target_odds * 1.05:  # tolleranza 5%
                acc.append(it)
                prod *= o
                if len(acc) >= min_picks and prod >= target_odds:
                    break
        return {"combo": acc, "combo_odds": prod}

    primary = combine_until_target(vp_sorted)
    # Alternative 1: favorisci edge alto
    alt1 = combine_until_target(sorted(vp, key=lambda x: float(x.get("edge") or 0.0), reverse=True))
    # Alternative 2: mix leghe diverse (greedy semplice)
    seen_leagues = set()
    mixed = []
    prod2 = 1.0
    for it in vp_sorted:
        lg = it.get("league")
        if lg not in seen_leagues and len(mixed) < max_picks:
            o = float(it.get("best_odds") or 1.0)
            if prod2 * o <= target_odds * 1.05:
                mixed.append(it)
                prod2 *= o
                seen_leagues.add(lg)
                if len(mixed) >= min_picks and prod2 >= target_odds:
                    break
    alt2 = {"combo": mixed, "combo_odds": prod2}

    return {
        "target_odds": target_odds,
        "min_picks": min_picks,
        "max_picks": max_picks,
        "primary": primary,
        "alternatives": [alt1, alt2],
    }

# ---------------------
# Nuovi endpoint
# ---------------------
@app.get("/events")
def events(range_days: int = Query(default=7, ge=1, le=14), league: Optional[str] = None):
    fixtures = _load_fixtures()
    # filtra per range
    now = datetime.now(timezone.utc)
    hi = now + timedelta(days=range_days)
    out = []
    for fx in fixtures:
        ko = fx.get("kickoff")
        try:
            ts = datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
        except Exception:
            ts = None
        if ts is None or not (now <= ts <= hi):
            continue
        if league and str(fx.get("league") or "").lower() != league.lower():
            continue
        out.append(fx)

    # arricchisci con best odds se disponibili
    odds_idx = _load_odds_by_fixture()
    for it in out:
        fid = str(it.get("fixture_id") or "")
        odds = odds_idx.get(fid)
        if odds and "best" in odds:
            it["best_odds"] = odds["best"]

    return {"count": len(out), "items": out}

@app.get("/value-picks")
def value_picks(edge_min: float = Query(default=0.03, ge=0.0, le=1.0)):
    return _compute_value_picks(edge_min=edge_min)

@app.post("/betslip/suggest")
def betslip_suggest(
    target_odds: float = Body(..., embed=True),
    min_picks: int = Body(2, embed=True),
    max_picks: int = Body(8, embed=True),
    edge_min: float = Body(0.03, embed=True),
):
    if target_odds < 1.1:
        raise HTTPException(status_code=400, detail="target_odds deve essere >= 1.1")
    return _suggest_betslip(target_odds=target_odds, min_picks=min_picks, max_picks=max_picks, edge_min=edge_min)

@app.get("/settings")
def get_settings():
    # Restituisci chiavi mascherate e parametri noti
    def mask(v: Optional[str]) -> str:
        if not v:
            return "(none)"
        v = str(v)
        return v[:4] + "…" if len(v) > 4 else v
    keys = {
        "FOOTBALL_DATA_API_KEY": mask(os.environ.get("FOOTBALL_DATA_API_KEY")),
        "ODDS_API_KEY": mask(os.environ.get("ODDS_API_KEY")),
        "TELEGRAM_API_ID": mask(os.environ.get("TELEGRAM_API_ID")),
        "TELEGRAM_API_HASH": mask(os.environ.get("TELEGRAM_API_HASH")),
    }
    params = {
        "TIMEZONE": os.environ.get("TIMEZONE", "Europe/Rome"),
        "FETCH_DAYS": os.environ.get("FETCH_DAYS", "7"),
        "LEAGUE_CODES": os.environ.get("LEAGUE_CODES", ""),
        "EFFECTIVE_THRESHOLD": os.environ.get("EFFECTIVE_THRESHOLD", "0.03"),
    }
    return {"keys": keys, "params": params, "data_dir": str(DATA_DIR)}

@app.post("/settings")
def set_settings(updates: Dict[str, str] = Body(...)):
    # Aggiorna .env con set_key (se disponibile) e ambiente di processo
    if not set_key or not find_dotenv:
        raise HTTPException(status_code=500, detail="python-dotenv non disponibile sul server")
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        # crea un nuovo .env nella root progetto (due livelli sopra this file)
        env_path = str((Path(__file__).resolve().parents[2] / ".env"))
    changed = {}
    for k, v in updates.items():
        if not isinstance(v, str):
            continue
        try:
            set_key(env_path, k, v, quote_mode="never")
            os.environ[k] = v
            changed[k] = True
        except Exception as e:
            changed[k] = f"error: {e}"
    return {"env": env_path, "changed": changed}

@app.get("/tipsters")
def get_tipsters():
    path = DATA_DIR / "telegram" / "tipsters.json"
    if not path.exists():
        # fallback seed
        seed_path = DATA_DIR / "telegram" / "tipsters_seed.json"
        if seed_path.exists():
            return load_json(seed_path)
        return {"items": []}
    return load_json(path)

@app.get("/tipsters/leaderboard")
def tipsters_leaderboard(range_days: int = Query(default=90, ge=1, le=365)):
    picks_path = DATA_DIR / "telegram" / "picks.jsonl"
    if not picks_path.exists():
        return {"items": []}
    items = load_jsonl(picks_path)
    now = datetime.now(timezone.utc)
    lo = now - timedelta(days=range_days)

    # KPI base per canale
    kpi: Dict[str, Dict[str, Any]] = {}
    for p in items:
        ch = str(p.get("channel") or "unknown")
        ts = p.get("timestamp")
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < lo:
            continue
        res = str(p.get("result") or "").lower()  # win/loss/pending
        odds = float(p.get("odds") or 0.0)
        stake = float(p.get("stake") or 1.0)
        if ch not in kpi:
            kpi[ch] = {"channel": ch, "win": 0, "loss": 0, "pending": 0, "picks": 0, "profit": 0.0}
        kpi[ch]["picks"] += 1
        if res == "win":
            kpi[ch]["win"] += 1
            if odds > 1.0:
                kpi[ch]["profit"] += (odds - 1.0) * stake
        elif res == "loss":
            kpi[ch]["loss"] += 1
            kpi[ch]["profit"] -= stake
        else:
            kpi[ch]["pending"] += 1

    out = []
    for ch, d in kpi.items():
        picks = max(1, d["picks"])
        hit_rate = d["win"] / picks
        roi = d["profit"] / picks
        out.append({"channel": ch, "picks": d["picks"], "win": d["win"], "loss": d["loss"], "pending": d["pending"], "hit_rate": hit_rate, "roi": roi, "profit": d["profit"]})
    out_sorted = sorted(out, key=lambda x: (x["roi"], x["hit_rate"], x["picks"]), reverse=True)
    return {"items": out_sorted}
