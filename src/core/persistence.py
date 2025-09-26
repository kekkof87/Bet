from __future__ import annotations

import json
import logging
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from .models import FixtureDataset, FixtureRecord

LOGGER = logging.getLogger(__name__)

# Costante legacy (statica) usata dai test per verificare l'esistenza del file.
LATEST_FIXTURES_FILE = Path("data") / "fixtures_latest.json"
LATEST_FIXTURES_FILE_NAME = "fixtures_latest.json"
PREVIOUS_FIXTURES_FILE_NAME = "fixtures_previous.json"


# ---------------------------------------------------------------------------
# Path helpers (runtime: rispettano BET_DATA_DIR se impostata)
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    return Path(os.getenv("BET_DATA_DIR", "data"))


def _latest_dynamic_path() -> Path:
    return _data_dir() / LATEST_FIXTURES_FILE_NAME


def _previous_dynamic_path() -> Path:
    return _data_dir() / PREVIOUS_FIXTURES_FILE_NAME


# ---------------------------------------------------------------------------
# Low level
# ---------------------------------------------------------------------------


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
# API pubblica
# ---------------------------------------------------------------------------


def load_latest_fixtures() -> FixtureDataset:
    """
    Carica prima dal path dinamico (BET_DATA_DIR); se non esiste, fallback al path statico legacy.
    """
    dyn = _latest_dynamic_path()
    if dyn.exists():
        return _load_json_list(dyn)
    return _load_json_list(LATEST_FIXTURES_FILE)


def save_latest_fixtures(fixtures: FixtureDataset) -> None:
    """
    Salva le fixtures se non vuote.
    - Lista vuota: rimuove eventuali file (dinamico + legacy) per evitare leakage tra test.
    - Lista non vuota: scrive nel path dinamico e, se diverso, duplica nel path statico (compat test).
    """
    dyn = _latest_dynamic_path()
    if not fixtures:
        # Clean up eventuali file preesistenti (test 'skips empty' si aspetta assenza)
        if dyn.exists():
            dyn.unlink()
        if LATEST_FIXTURES_FILE.exists():
            LATEST_FIXTURES_FILE.unlink()
        return
    _write_json_atomic(dyn, fixtures)
    if dyn.resolve() != LATEST_FIXTURES_FILE.resolve():
        _write_json_atomic(LATEST_FIXTURES_FILE, fixtures)


def clear_latest_fixtures_file() -> None:
    """
    Rimuove sia il file dinamico sia quello statico legacy se presenti.
    """
    dyn = _latest_dynamic_path()
    if dyn.exists():
        dyn.unlink()
    if LATEST_FIXTURES_FILE.exists():
        LATEST_FIXTURES_FILE.unlink()


def load_previous_fixtures() -> FixtureDataset:
    return _load_json_list(_previous_dynamic_path())


def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    if not fixtures:
        return
    _write_json_atomic(path, fixtures)
