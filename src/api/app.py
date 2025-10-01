from __future__ import annotations

from fastapi import FastAPI

from core.config import get_settings
from core.logging import get_logger

from api.routes.health import router as health_router
from api.routes.fixtures import router as fixtures_router
from api.routes.delta import router as delta_router
from api.routes.scoreboard import router as scoreboard_router
from api.routes.metrics import router as metrics_router
from api.routes.predictions import router as predictions_router
from api.routes.consensus import router as consensus_router
from api.routes.value_alerts import router as value_alerts_router
from api.routes.roi import router as roi_router

logger = get_logger("api.app")


def create_app() -> FastAPI:
    app = FastAPI(title="Bet Pipeline API", version="0.1.0")
    try:
        get_settings()
    except Exception as exc:  # pragma: no cover
        logger.error("Impossibile caricare settings: %s", exc)

    app.include_router(health_router)
    app.include_router(fixtures_router)
    app.include_router(delta_router)
    app.include_router(scoreboard_router)
    app.include_router(metrics_router)
    app.include_router(predictions_router)
    app.include_router(consensus_router)
    app.include_router(value_alerts_router)
    app.include_router(roi_router)
    return app


app = create_app()
