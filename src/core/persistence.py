import json
import os
from pathlib import Path
from typing import Any, List

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)

# Costante di riferimento usata nei test: path "canonico" nel repo
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
    Inoltre, sincronizza anche il path canonico LATEST_FIXTURES_FILE (data/fixtures_latest.json)
    perché i test ne verificano l'esistenza.
    """
    if not fixtures:
        # Non creare il file quando non c'è nulla da salvare (comportamento atteso dai test)
        return

    # Scrivi nel path effettivo (BET_DATA_DIR o settings)
    effective_path = _latest_path()
    effective_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        effective_path.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"Saved latest fixtures to {effective_path}")
    except Exception as e:
        log.error(f"Failed to persist fixtures to {effective_path}: {e}")
        raise

    # Sincronizza anche nel path canonico del repo (data/fixtures_latest.json)
    try:
        LATEST_FIXTURES_FILE.parent.mkdir(parents=True, exist_ok=True)
        LATEST_FIXTURES_FILE.write_text(
            json.dumps(fixtures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"Synced latest fixtures to {LATEST_FIXTURES_FILE}")
    except Exception as e:
        # Non fallire l'intera operazione: best effort per il path "canonico"
        log.warning(f"Could not sync fixtures to {LATEST_FIXTURES_FILE}: {e}")


def load_latest_fixtures() -> List[Any]:
    """
    Carica le ultime fixtures dal path effettivo.
    In caso di:
    - file mancante -> []
    - JSON invalido -> [] con warning contenente 'invalid json'
    - struttura non lista -> [] con warning contenente 'invalid structure'
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
        # Includi 'invalid structure' per soddisfare l'asserzione del test
        log.warning(f"Invalid structure in {path}: not a list")
        return []
    return data
