from __future__ import annotations

import json
import logging
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from .models import FixtureDataset, FixtureRecord

LOGGER = logging.getLogger(__name__)

# Legacy constant (STATIC). Usata dai test solo per un check di esistenza.
# Le funzioni runtime usano invece il path dinamico basato su BET_DATA_DIR.
LATEST_FIXTURES_FILE = Path("data") / "fixtures_latest.json"
PREVIOUS_FIXTURES_FILE_NAME = "fixtures_previous.json"
LATEST_FIXTURES_FILE_NAME = "fixtures_latest.json"


def _data_dir() -> Path:
    """
    Directory dinamica per i dati; dipende da BET_DATA_DIR (default: 'data').
    Lettura a ogni chiamata per permettere ai test di cambiare ENV dopo import.
    """
    return Path(os.getenv("BET_DATA_DIR", "data"))


def _latest_path() -> Path:
    return _data_dir() / LATEST_FIXTURES_FILE_NAME


def _previous_path() -> Path:
    return _data_dir() / PREVIOUS_FIXTURES_FILE_NAME


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json_atomic(path: Path, data: Any, indent: int = 2) -> None:
    _ensure_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _load_json_list(path: Path) -> FixtureDataset:
    """
    Ritorna sempre una lista (anche vuota).
    Logga warning se file corrotto o struttura non-list.
    """
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except JSONDecodeError:
        LOGGER.warning("Invalid / corrupt fixtures JSON at %s", path)
        return []
    except OSError as e:
        LOGGER.warning("Error reading fixtures file %s: %s", path, e)
        return []
    if not isinstance(raw, list):
        LOGGER.warning("Invalid structure in fixtures JSON (expected list) at %s", path)
        return []
    out: FixtureDataset = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------------------
# API pubblica (dinamica rispetto a BET_DATA_DIR)
# ---------------------------------------------------------------------------


def load_latest_fixtures() -> FixtureDataset:
    return _load_json_list(_latest_path())


def save_latest_fixtures(fixtures: FixtureDataset) -> None:
    """
    Non crea il file se la lista è vuota (richiesto dai test).
    """
    if not fixtures:
        return
    _write_json_atomic(_latest_path(), fixtures)


def clear_latest_fixtures_file() -> None:
    path = _latest_path()
    if path.exists():
        path.unlink()


def load_previous_fixtures() -> FixtureDataset:
    return _load_json_list(_previous_path())


def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    if not fixtures:
        return
    _write_json_atomic(path, fixtures)
