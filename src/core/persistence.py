import json
import os
from pathlib import Path
from typing import Any, List

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)

# Costante di riferimento usata nei test per verifiche sull'albero del repo
LATEST_FIXTURES_FILE = Path("data") / "fixtures_latest.json"


def _effective_data_dir() -> Path:
    """
    Directory effettiva in cui leggere/scrivere, rispettando l'ambiente di test.
    Priorità:
    - BET_DATA_DIR in env (usata dai test)
    - settings.bet_data_dir
    """
    env_dir = os.getenv("BET_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(get_settings().bet_data_dir)


def _latest_path() -> Path:
    return _effective_data_dir() / "fixtures_latest.json"


def save_latest_fixtures(fixtures: List[Any]) -> None:
    """
    Salva le ultime fixtures nel file effettivo. Se la lista è vuota, non crea/aggiorna il file.
    """
    if not fixtures:
        # Non creare il file quando non c'è nulla da salvare (comportamento atteso dai test)
        return
    path = _latest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"Saved latest fixtures to {path}")
    except Exception as e:
        log.error(f"Failed to persist fixtures to {path}: {e}")
        raise


def load_latest_fixtures() -> List[Any]:
    """
    Carica le ultime fixtures. In caso di:
    - file mancante -> []
    - JSON invalido -> [] con warning
    - struttura non lista -> [] con warning
    """
    path = _latest_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"Invalid JSON in {path}: {e}")
        return []
    if not isinstance(data, list):
        log.warning(f"Unexpected structure in {path}: not a list")
        return []
    return data
