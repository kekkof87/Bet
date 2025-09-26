from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Optional
from .models import FixtureDataset

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
    # (Opzionale) Validazione superficiale
    return data  # type: ignore[return-value]

def save_fixtures_atomic(path: Path, fixtures: FixtureDataset) -> None:
    write_json_atomic(path, fixtures)
