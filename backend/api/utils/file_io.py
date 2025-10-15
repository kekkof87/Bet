import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Cache molto semplice basata su mtime
_CACHE: Dict[str, Dict[str, Any]] = {}
_TTL_SEC = 10

def _load_raw(path: Path) -> Any:
    with path.open("rb") as f:
        return json.load(f)

def load_json(path: Path) -> Any:
    key = str(path.resolve())
    now = time.time()
    entry = _CACHE.get(key)
    try:
        stat = path.stat()
    except FileNotFoundError:
        raise
    if entry and (now - entry["ts"] < _TTL_SEC) and entry["mtime"] == stat.st_mtime_ns:
        return entry["data"]
    data = _load_raw(path)
    _CACHE[key] = {"ts": now, "mtime": stat.st_mtime_ns, "data": data}
    return data

def load_jsonl(path: Path) -> List[Any]:
    key = f"{path.resolve()}::jsonl"
    now = time.time()
    entry = _CACHE.get(key)
    try:
        stat = path.stat()
    except FileNotFoundError:
        raise
    if entry and (now - entry["ts"] < _TTL_SEC) and entry["mtime"] == stat.st_mtime_ns:
        return entry["data"]
    items: List[Any] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                # mantieni la riga raw se non è un JSON valido
                items.append({"raw": line})
    _CACHE[key] = {"ts": now, "mtime": stat.st_mtime_ns, "data": items}
    return items

def filter_by_status(items: List[dict], statuses: List[str]) -> List[dict]:
    sset = {s.upper() for s in statuses}
    out = []
    for it in items:
        st = str(it.get("status", "")).upper()
        if st in sset:
            out.append(it)
    return out

def filter_predictions(
    items: List[dict],
    min_edge: Optional[float],
    active_only: bool,
    status: Optional[List[str]],
) -> List[dict]:
    out = items
    if min_edge is not None:
        out = [x for x in out if float(x.get("edge", 0)) >= min_edge]
    if active_only:
        out = [x for x in out if x.get("value", {}).get("active", False)]
    if status:
        sset = {s.upper() for s in status}
        out = [x for x in out if str(x.get("status", x.get("fixture", {}).get("status", ""))).upper() in sset]
    return out
