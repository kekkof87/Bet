from __future__ import annotations

from fastapi import APIRouter
from core.config import get_settings

router = APIRouter(tags=["health"])

@router.get("/health", summary="Health check")
def health():
    """
    Health endpoint minimale.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "predictions_enabled": settings.enable_predictions,
        "odds_ingestion_enabled": settings.enable_odds_ingestion,
        "value_detection_enabled": settings.enable_value_detection,
    }
