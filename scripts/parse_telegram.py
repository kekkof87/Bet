from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from core.config import get_settings
from core.logging import get_logger
from telegram.parser import parse_messages, write_parsed_events

logger = get_logger("scripts.parse_telegram")


def load_raw_messages(path: Path) -> List[str]:
    if not path.exists():
        logger.error("File non trovato: %s", path)
        return []
    lines = [l.rstrip("\n") for l in path.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l.strip()]


def main() -> None:
    """
    Esempio di utilizzo:
      ENABLE_TELEGRAM_PARSER=1 python -m scripts.parse_telegram path/al/file.txt
    Il file contiene un messaggio per riga.
    """
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.parse_telegram <file_messaggi.txt>")
        return
    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("Config non valida: %s", e)
        return

    fpath = Path(sys.argv[1])
    raw_msgs = load_raw_messages(fpath)
    if not raw_msgs:
        logger.warning("Nessun messaggio da elaborare.")
        return

    events = parse_messages(raw_msgs)
    logger.info("parsed_telegram_events", extra={"count": len(events)})

    if settings.enable_telegram_parser:
        out = write_parsed_events(events)
        if out:
            logger.info("parsed_events_written", extra={"path": str(out)})
    else:
        logger.info("Parser disabilitato: set ENABLE_TELEGRAM_PARSER=1 per scrivere output.")


if __name__ == "__main__":
    main()
