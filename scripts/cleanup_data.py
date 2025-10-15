from __future__ import annotations

import os
from pathlib import Path

from core.config import get_settings
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
    s = get_settings()
    base = Path(s.bet_data_dir or "data")
    history_max = _int_env("DATA_RETENTION_HISTORY_MAX", s.history_max if s.history_max > 0 else 30)

    # Ruota history fixtures (usa helper esistente)
    rotate_history(history_max)

    # Rimuovi .tmp orfani
    for p in base.rglob("*.tmp"):
        try:
            p.unlink()
        except Exception:
            pass

    log.info("Cleanup completato. history_max=%d", history_max)


if __name__ == "__main__":
    main()
