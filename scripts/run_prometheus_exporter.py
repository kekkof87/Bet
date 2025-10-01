from __future__ import annotations

import time
from prometheus_client import start_http_server
from core.config import get_settings
from core.logging import get_logger
from monitoring.prometheus_exporter import update_prom_metrics

logger = get_logger("scripts.run_prometheus_exporter")


def main() -> None:
    try:
        settings = get_settings()
    except ValueError as e:
        logger.error("Config non valida: %s", e)
        return

    if not settings.enable_prometheus_exporter:
        logger.error("ENABLE_PROMETHEUS_EXPORTER=0: nulla da fare.")
        return

    port = settings.prometheus_port
    start_http_server(port)
    logger.info("Prometheus exporter avviato", extra={"port": port})

    # Loop semplice: rilegge i file e aggiorna metriche ogni 15s
    while True:
        try:
            update_prom_metrics()
        except Exception as exc:  # pragma: no cover
            logger.error("Errore update metrics: %s", exc)
        time.sleep(15)


if __name__ == "__main__":
    main()
