from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .models import FixtureDataset

# Directory & file naming (puoi adattare se altrove)
DATA_DIR = Path("data")
LATEST_FIXTURES_FILE = DATA_DIR / "fixtures_latest.json"
PREVIOUS_FIXTURES_FILE = DATA_DIR / "fixtures_previous.json"


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_atomic(path: Path, data: Any, indent: int = 2) -> None:
    ensure_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_fixtures(path: Path) -> Optional[FixtureDataset]:
    if not path.exists():
        return None
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError("Invalid fixtures file: expected list")
    # Validazione leggera differibile; ritorno tipizzato
    return data  # FixturesDataset alias list[FixtureRecord]


def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    write_json_atomic(path, fixtures)


# ---------------------------------------------------------------------------
# Backward compatibility wrappers (usati dai provider & test esistenti)
# ---------------------------------------------------------------------------

def save_latest_fixtures(fixtures: FixtureDataset) -> None:
    """
    Wrapper retro-compatibile.
    Usa la write atomica sul file 'fixtures_latest.json'.
    """
    save_fixtures_atomic(LATEST_FIXTURES_FILE, fixtures)


def clear_latest_fixtures_file() -> None:
    """
    Elimina il file delle fixtures correnti se esiste.
    Usato in alcuni test per ripulire stato.
    """
    if LATEST_FIXTURES_FILE.exists():
        LATEST_FIXTURES_FILE.unlink()


def load_latest_fixtures() -> Optional[FixtureDataset]:
    return load_fixtures(LATEST_FIXTURES_FILE)
