from __future__ import annotations

import json
import logging
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Optional

from .models import FixtureDataset, FixtureRecord

LOGGER = logging.getLogger(__name__)

# Cartella dati (può essere resa dinamica in futuro leggendo da settings/env)
DATA_DIR = Path("data")

# File “corrente” usato nei test e dal provider
LATEST_FIXTURES_FILE = DATA_DIR / "fixtures_latest.json"
PREVIOUS_FIXTURES_FILE = DATA_DIR / "fixtures_previous.json"


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_atomic(path: Path, data: Any, indent: int = 2) -> None:
    """
    Scrittura atomica: crea file temporaneo e poi sostituisce quello reale.
    """
    ensure_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Funzioni di basso livello (non usate direttamente dai test)
# ---------------------------------------------------------------------------


def _load_json_list(path: Path) -> FixtureDataset:
    """
    Carica una lista JSON dal path. Se invalido o struttura errata → log + [].
    """
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except JSONDecodeError:
        LOGGER.warning("Invalid / corrupt fixtures JSON at %s", path)
        return []
    except OSError as e:
        LOGGER.warning("Error reading fixtures file %s: %s", path, e)
        return []
    if not isinstance(data, list):
        LOGGER.warning("Invalid structure in fixtures JSON (expected list) at %s", path)
        return []
    # Validazione superficiale opzionale: controlliamo chiave fixture_id se presente
    out: FixtureDataset = []
    for item in data:
        if isinstance(item, dict):
            # Non facciamo casting rigido ora; i test richiedono solo la lista
            out.append(item)  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------------------
# API pubblica compatibile con i test esistenti
# ---------------------------------------------------------------------------


def load_latest_fixtures() -> FixtureDataset:
    """
    Ritorna sempre una lista (vuota se il file manca o è invalido).
    """
    return _load_json_list(LATEST_FIXTURES_FILE)


def save_latest_fixtures(fixtures: FixtureDataset) -> None:
    """
    Salva la lista solo se NON vuota. (Comportamento atteso dai test.)
    """
    if not fixtures:  # lista vuota → no file
        return
    write_json_atomic(LATEST_FIXTURES_FILE, fixtures)


def clear_latest_fixtures_file() -> None:
    """
    Elimina il file corrente se esiste (usato nei test).
    """
    if LATEST_FIXTURES_FILE.exists():
        LATEST_FIXTURES_FILE.unlink()


# Funzione aggiuntiva (non richiesta dai test ma utile).
def load_previous_fixtures() -> FixtureDataset:
    return _load_json_list(PREVIOUS_FIXTURES_FILE)


def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    """
    API generica (rimane disponibile per codice futuro).
    """
    if not fixtures:
        return
    write_json_atomic(path, fixtures)
