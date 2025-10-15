from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from .models import FixtureDataset

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File names / legacy constants
# ---------------------------------------------------------------------------
LATEST_FIXTURES_FILE = Path("data") / "fixtures_latest.json"  # legacy static path (kept for backward compatibility in tests)
LATEST_FIXTURES_FILE_NAME = "fixtures_latest.json"
PREVIOUS_FIXTURES_FILE_NAME = "fixtures_previous.json"
HISTORY_DIR_NAME = "history"  # directory (inside BET_DATA_DIR) for timestamped snapshots

# ---------------------------------------------------------------------------
# Path helpers (runtime: rispettano BET_DATA_DIR se impostata)
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    return Path(os.getenv("BET_DATA_DIR", "data"))


def _latest_dynamic_path() -> Path:
    return _data_dir() / LATEST_FIXTURES_FILE_NAME


def _previous_dynamic_path() -> Path:
    return _data_dir() / PREVIOUS_FIXTURES_FILE_NAME


def _history_dir() -> Path:
    return _data_dir() / HISTORY_DIR_NAME


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
# Latest / Previous
# ---------------------------------------------------------------------------


def load_latest_fixtures() -> FixtureDataset:
    """
    Carica le fixtures più recenti.
    - Se esiste il file nel path dinamico (BET_DATA_DIR), usa quello.
    - Se NON esiste:
        - Esegui fallback al path statico legacy (data/fixtures_latest.json) SOLO
          se BET_DATA_DIR non è impostata o è "data".
        - Se BET_DATA_DIR è impostata ad un path diverso, NON fare fallback e ritorna [].
      Questo evita leakage tra test che ridefiniscono BET_DATA_DIR.
    """
    dyn = _latest_dynamic_path()
    if dyn.exists():
        return _load_json_list(dyn)

    bet_dir_env = os.getenv("BET_DATA_DIR")
    if bet_dir_env is None or bet_dir_env.strip() in ("", "data", "./data", "./data/"):
        return _load_json_list(LATEST_FIXTURES_FILE)

    # BET_DATA_DIR è impostata a una directory diversa: no fallback legacy
    return []


def save_latest_fixtures(fixtures: FixtureDataset) -> None:
    """
    Salva le fixtures se non vuote.
    - Lista vuota: rimuove eventuali file (dinamico + legacy) per evitare leakage tra test.
    - Lista non vuota: scrive nel path dinamico e, se diverso, duplica nel path statico (compat test).
    """
    dyn = _latest_dynamic_path()
    if not fixtures:
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
    """
    Carica lo snapshot previous (se esiste), altrimenti lista vuota.
    """
    return _load_json_list(_previous_dynamic_path())


def save_previous_fixtures(fixtures: FixtureDataset) -> None:
    """
    Salva lo snapshot precedente (previous) per audit / diff.
    - Non salva se la lista è vuota.
    - Sovrascrive sempre il file esistente.
    """
    if not fixtures:
        return
    _write_json_atomic(_previous_dynamic_path(), fixtures)


def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    """
    Utility generica (attualmente non usata esternamente) per salvataggi diretti.
    """
    if not fixtures:
        return
    _write_json_atomic(path, fixtures)


# ---------------------------------------------------------------------------
# History snapshots
# ---------------------------------------------------------------------------


def save_history_snapshot(fixtures: FixtureDataset) -> Path:
    """
    Salva uno snapshot timestamped se fixtures non vuote.
    Ritorna il path creato, oppure un path fittizio (history/empty-skip) se lista vuota.
    Usa timestamp con microsecondi per evitare collisioni nello stesso secondo.
    In caso (estremo) di collisione sul nome, aggiunge un contatore suffisso.
    """
    if not fixtures:
        return _history_dir() / "empty-skip"

    # Assicura esistenza directory
    _ensure_dir(_history_dir() / "._probe")

    base_stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    attempt = 0
    while True:
        suffix = f"_{attempt}" if attempt > 0 else ""
        path = _history_dir() / f"fixtures_{base_stamp}{suffix}.json"
        if not path.exists():
            _write_json_atomic(path, fixtures)
            return path
        attempt += 1  # extremely unlikely


def rotate_history(max_files: int) -> None:
    """
    Mantiene al più max_files snapshot nella cartella history (ordine alfabetico ≈ ordine temporale).
    Rimuove i più vecchi se eccedenti.
    """
    hdir = _history_dir()
    if not hdir.exists():
        return
    files = sorted(
        (p for p in hdir.iterdir() if p.is_file() and p.name.startswith("fixtures_")),
        key=lambda p: p.name,
    )
    excess = len(files) - max_files
    if excess <= 0:
        return
    for old in files[:excess]:
        try:
            old.unlink()
        except OSError:
            LOGGER.warning("Impossibile rimuovere snapshot history: %s", old)
