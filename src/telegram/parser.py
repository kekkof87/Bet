from __future__ import annotations

import re
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("telegram.parser")

GOAL_PATTERNS = [
    re.compile(r"\bGOAL\b", re.IGNORECASE),
    re.compile(r"\bGOL!\b", re.IGNORECASE),
    re.compile(r"\b(?:⚽|🅶|🅖)\b"),
]

SCORE_PATTERN = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
# Possibili mention squadra semplice (uppercase words) oppure vs separator
TEAM_SPLIT_PATTERN = re.compile(r"(?i)(?:^|\s)([A-Z][A-Za-z0-9_. ]{2,25})\s+vs\s+([A-Z][A-Za-z0-9_. ]{2,25})")
STATUS_PATTERN = re.compile(r"\b(HT|FT|1H|2H|ET|AET|P)\b")

FIXTURE_ID_INLINE = re.compile(r"\bfixture[_ ]?id[:=]\s*(\d+)", re.IGNORECASE)


@dataclass
class TelegramEvent:
    raw_text: str
    type: str
    fixture_id: Optional[int]
    home_score: Optional[int]
    away_score: Optional[int]
    status: Optional[str]
    detected_at: str


def is_goal(text: str) -> bool:
    return any(p.search(text) for p in GOAL_PATTERNS)


def extract_score(text: str) -> tuple[Optional[int], Optional[int]]:
    m = SCORE_PATTERN.search(text)
    if not m:
        return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except Exception:
        return None, None


def extract_status(text: str) -> Optional[str]:
    m = STATUS_PATTERN.search(text)
    return m.group(1) if m else None


def extract_fixture_id(text: str) -> Optional[int]:
    m = FIXTURE_ID_INLINE.search(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # fallback euristico: se c'è un numero a 5-7 cifre fuori contesto
    m2 = re.search(r"\b(\d{5,7})\b", text)
    if m2:
        try:
            return int(m2.group(1))
        except ValueError:
            return None
    return None


def classify_message(text: str) -> Optional[str]:
    if is_goal(text):
        return "goal"
    st = extract_status(text)
    if st:
        return "status"
    if SCORE_PATTERN.search(text):
        return "score_update"
    return None


def parse_messages(messages: List[str]) -> List[Dict[str, Any]]:
    now_iso = datetime.now(timezone.utc).isoformat()
    events: List[Dict[str, Any]] = []
    for m in messages:
        ttype = classify_message(m)
        if not ttype:
            continue
        hs, as_ = extract_score(m)
        status = extract_status(m)
        fixture_id = extract_fixture_id(m)
        events.append(
            {
                "raw_text": m,
                "type": ttype,
                "fixture_id": fixture_id,
                "home_score": hs,
                "away_score": as_,
                "status": status,
                "detected_at": now_iso,
            }
        )
    return events


def write_parsed_events(events: List[Dict[str, Any]]) -> Optional[Path]:
    settings = get_settings()
    if not settings.enable_telegram_parser:
        logger.info("Telegram parser disabilitato (ENABLE_TELEGRAM_PARSER=0)")
        return None
    base = Path(settings.bet_data_dir or "data")
    out_dir = base / settings.telegram_parsed_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "last_parsed.json"
    tmp = target.with_suffix(".tmp")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(events),
        "events": events,
    }
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


__all__ = [
    "parse_messages",
    "write_parsed_events",
    "classify_message",
    "extract_score",
    "extract_status",
    "extract_fixture_id",
]
