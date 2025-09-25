from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any

log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("BET_DATA_DIR", "data"))
LATEST_FIXTURES_FILE = DATA_DIR / "fixtures_latest.json"


def save_latest_fixtures(fixtures: List[Dict[str, Any]]) -> None:
    if not fixtures:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with LATEST_FIXTURES_FILE.open("w", encoding="utf-8") as f:
            json.dump(fixtures, f, ensure_ascii=False, indent=2)
        log.info(f"persist fixtures count={len(fixtures)} path={LATEST_FIXTURES_FILE}")
    except Exception as e:
        log.error(f"persist fixtures failed error={e}")


def load_latest_fixtures() -> List[Dict[str, Any]]:
    if not LATEST_FIXTURES_FILE.exists():
        return []
    try:
        with LATEST_FIXTURES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        log.warning("latest fixtures file invalid structure (not a list)")
        return []
    except json.JSONDecodeError:
        log.warning("latest fixtures file invalid/corrupt JSON")
        return []
    except Exception as e:
        log.warning(f"latest fixtures file read error={e}")
        return []
