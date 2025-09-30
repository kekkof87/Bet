from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("core.alerts")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _scores(old: Dict[str, Any], new: Dict[str, Any]) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    return (
        old.get("home_score"),
        old.get("away_score"),
        new.get("home_score"),
        new.get("away_score"),
    )


def _status(old: Dict[str, Any], new: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    return old.get("status"), new.get("status")


def build_alerts(modified: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Costruisce lista di alert a partire da modifiche (lista di dict con chiavi old/new).
    Tipi generati:
      - score_update: uno dei punteggi cambia
      - status_transition: status cambia seguendo una sequenza forward definita
    Se la configurazione (API_FOOTBALL_KEY) non è disponibile, usa fallback di default.
    """
    # Default sequence & flags
    default_seq = ["NS", "1H", "HT", "2H", "ET", "P", "AET", "FT"]
    seq = default_seq
    include_final = True

    # Prova a caricare settings per parametri personalizzati
    try:
        settings = get_settings()
        seq = settings.alert_status_sequence or default_seq
        include_final = settings.alert_include_final
    except Exception:
        # Fallback silenzioso – nessuna API key / config necessaria per generare alert basici
        logger.debug("build_alerts: uso fallback default (config non disponibile)")

    seq_index = {s: i for i, s in enumerate(seq)}

    events: List[Dict[str, Any]] = []
    for m in modified:
        old = m.get("old") or {}
        new = m.get("new") or {}
        fixture_id = new.get("fixture_id") or old.get("fixture_id")

        o_h, o_a, n_h, n_a = _scores(old, new)
        # Score update: cambia almeno un punteggio
        if (o_h, o_a) != (n_h, n_a) and (n_h is not None or n_a is not None):
            events.append(
                {
                    "type": "score_update",
                    "fixture_id": fixture_id,
                    "old_score": f"{o_h}-{o_a}",
                    "new_score": f"{n_h}-{n_a}",
                    "status": new.get("status"),
                }
            )

        # Status transition: cambio forward nella sequenza
        o_st, n_st = _status(old, new)
        if o_st != n_st and n_st:
            if o_st in seq_index and n_st in seq_index:
                if seq_index[n_st] >= seq_index[o_st]:
                    if include_final or n_st != "FT":
                        events.append(
                            {
                                "type": "status_transition",
                                "fixture_id": fixture_id,
                                "from": o_st,
                                "to": n_st,
                            }
                        )

    return events


def write_alerts(events: List[Dict[str, Any]]) -> Optional[Path]:
    """
    Scrive alerts/last_alerts.json se abilitato e ci sono eventi.
    Se la config non è disponibile o disabilitato → ritorna None senza errori.
    """
    try:
        settings = get_settings()
    except Exception:
        # Config non disponibile → nessun salvataggio
        logger.debug("write_alerts: config non disponibile, skip salvataggio")
        return None

    if not settings.enable_alerts_file or not events:
        return None

    base = Path(settings.bet_data_dir or "data")
    alerts_dir = base / settings.alerts_dir
    _ensure_dir(alerts_dir)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
        "count": len(events),
    }
    target = alerts_dir / "last_alerts.json"
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


__all__ = ["build_alerts", "write_alerts"]
