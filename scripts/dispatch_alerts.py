from __future__ import annotations

from core.config import get_settings
from core.logging import get_logger
from notifications.dispatcher import load_alert_events, dispatch_alerts

logger = get_logger("scripts.dispatch_alerts")


def main() -> None:
    try:
        get_settings()
    except ValueError as e:
        logger.error("Config non valida: %s", e)
        return

    events = load_alert_events()
    if not events:
        logger.info("Nessun alert da inviare.")
        return
    count = dispatch_alerts(events)
    logger.info("Alert dispatch completato", extra={"count": count})


if __name__ == "__main__":
    main()
