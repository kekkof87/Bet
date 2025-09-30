from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


EXTRA_WHITELIST = {"delta_summary", "fetch_stats", "change_breakdown"}


class JsonFormatter(logging.Formatter):
    """Formatter JSON con supporto campi extra selezionati."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Extra whitelisted
        for key in EXTRA_WHITELIST:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
