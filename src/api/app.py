from __future__ import annotations

from fastapi import FastAPI

from core.config import get_settings
from core.logging import get_logger

# Router esistenti (placeholder – mantieni gli altri import se li avevi)
# from api.routes.health import router as health_router
# from api.routes.fixtures import router as fixtures_router
# from api.routes.delta import router as delta_router
# from api.routes.scoreboard import router as scoreboard_router

from api.routes.predictions import router as predictions_router  # NEW

logger = get_logger("api.app")


def create_app() -> FastAPI:
    app = FastAPI(title="Bet Pipeline API", version="0.1.0")
    try:
        get_settings()
    except Exception as exc:  # pragma: no cover
        logger.error("Impossibile caricare settings: %s", exc)

    # Registrazione router esistenti (decommenta se presenti nel tuo repo)
    # app.include_router(health_router)
    # app.include_router(fixtures_router)
    # app.include_router(delta_router)
    # app.include_router(scoreboard_router)
    app.include_router(predictions_router)

    return app


app = create_app()
