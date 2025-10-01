from __future__ import annotations

import json
import time
from typing import List, Dict, Any, Optional

import requests

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("notifications.dispatcher")


def load_alert_events(base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    base = settings.bet_data_dir or "data"
    if base_dir:
        base = base_dir
    path = f"{base}/{settings.alerts_dir}/last_alerts.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("events") or []
        if not isinstance(events, list):
            return []
        return [e for e in events if isinstance(e, dict)]
    except FileNotFoundError:
        logger.info("Nessun file alerts da dispatchare (%s).", path)
    except Exception as exc:  # pragma: no cover
        logger.error("Errore lettura alerts: %s", exc)
    return []


def _format_event_line(ev: Dict[str, Any]) -> str:
    etype = ev.get("type")
    fid = ev.get("fixture_id")
    status = ev.get("status")
    if etype == "score_update":
        old_s = ev.get("old_score")
        new_s = ev.get("new_score")
        return f"[SCORE] fixture={fid} {old_s} -> {new_s} status={status}"
    if etype == "status_transition":
        frm = ev.get("from")
        to = ev.get("to")
        return f"[STATUS] fixture={fid} {frm} -> {to}"
    return f"[EVENT] fixture={fid} type={etype}"


def _dispatch_stdout(events: List[Dict[str, Any]]) -> None:
    for ev in events:
        logger.info("alert_dispatch_stdout", extra={"alert_line": _format_event_line(ev)})


def _dispatch_webhook(events: List[Dict[str, Any]], url: str) -> None:
    payload = {
        "dispatched_at": int(time.time()),
        "count": len(events),
        "events": events,
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        logger.info("alert_dispatch_webhook", extra={"url": url, "status": r.status_code})
    except Exception as exc:  # pragma: no cover
        logger.error("Errore webhook dispatch: %s", exc)


def _dispatch_telegram(events: List[Dict[str, Any]], token: str, chat_id: str) -> None:
    base_url = f"https://api.telegram.org/bot{token}/sendMessage"
    for ev in events:
        text = _format_event_line(ev)
        try:
            r = requests.post(base_url, data={"chat_id": chat_id, "text": text}, timeout=5)
            logger.info("alert_dispatch_telegram", extra={"status": r.status_code})
        except Exception as exc:  # pragma: no cover
            logger.error("Errore telegram dispatch: %s", exc)


def dispatch_alerts(events: List[Dict[str, Any]]) -> int:
    """
    Ritorna il numero di eventi inviati (o loggati).
    """
    if not events:
        logger.info("Nessun evento da dispatchare.")
        return 0
    settings = get_settings()
    if not settings.enable_alert_dispatch:
        logger.info("Alert dispatch disabilitato (ENABLE_ALERT_DISPATCH=0).")
        return 0

    mode = settings.alert_dispatch_mode
    logger.info("Avvio dispatch alerts", extra={"mode": mode, "events": len(events)})

    if mode == "stdout":
        _dispatch_stdout(events)
    elif mode == "webhook":
        if not settings.alert_webhook_url:
            logger.error("ALERT_WEBHOOK_URL mancante, fallback stdout.")
            _dispatch_stdout(events)
        else:
            _dispatch_webhook(events, settings.alert_webhook_url)
    elif mode == "telegram":
        if not (settings.alert_telegram_bot_token and settings.alert_telegram_chat_id):
            logger.error("Token/chat Telegram mancanti, fallback stdout.")
            _dispatch_stdout(events)
        else:
            _dispatch_telegram(events, settings.alert_telegram_bot_token, settings.alert_telegram_chat_id)
    else:
        logger.error("Modalità dispatch '%s' non riconosciuta, fallback stdout.", mode)
        _dispatch_stdout(events)

    return len(events)


__all__ = ["load_alert_events", "dispatch_alerts"]
