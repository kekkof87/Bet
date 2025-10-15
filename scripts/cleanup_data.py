from __future__ import annotations

import os
from pathlib import Path

from core.logging import get_logger
from core.persistence import rotate_history

log = get_logger("scripts.cleanup_data")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> None:
    base = Path(os.getenv("BET_DATA_DIR", "data"))
    history_max = _int_env("DATA_RETENTION_HISTORY_MAX", 30)

    # Ruota history fixtures (usa helper che rispetta BET_DATA_DIR)
    rotate_history(history_max)

    # Rimuovi .tmp orfani sotto BET_DATA_DIR
    if base.exists():
        for p in base.rglob("*.tmp"):
            try:
                p.unlink()
            except Exception:
                pass

    log.info("Cleanup completato. base=%s history_max=%d", str(base), history_max)


if __name__ == "__main__":
    main()
