#!/usr/bin/env python3
import os
from dataclasses import dataclass
from typing import Optional

def _bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1","true","yes","y","on"}

def _float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def _int(v: str, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default

@dataclass
class Config:
    DATA_DIR: str = os.environ.get("DATA_DIR", "data")
    ODDS_PROVIDER: str = os.environ.get("ODDS_PROVIDER", "model")  # "model" | "external"
    ENABLE_ODDS_INGESTION: bool = _bool(os.environ.get("ENABLE_ODDS_INGESTION", "1"), True)
    MODEL_ODDS_MARGIN: float = _float(os.environ.get("MODEL_ODDS_MARGIN", "0.0"), 0.0)  # maggiorazione opzionale
    EFFECTIVE_THRESHOLD: float = _float(os.environ.get("EFFECTIVE_THRESHOLD", "0.03"), 0.03)
    ALERTS_FILTER_STATUS: Optional[str] = os.environ.get("ALERTS_FILTER_STATUS")  # es: "NS,1H"
    ALERT_DISPATCH_WEBHOOK: Optional[str] = os.environ.get("ALERT_DISPATCH_WEBHOOK")  # Slack/Webhook
    RETENTION_DAYS: int = _int(os.environ.get("RETENTION_DAYS", "14"), 14)

def validate(cfg: Config) -> None:
    errors = []
    if cfg.ODDS_PROVIDER not in {"model","external"}:
        errors.append(f"ODDS_PROVIDER deve essere 'model' o 'external', trovato: {cfg.ODDS_PROVIDER}")
    if not (0.0 <= cfg.EFFECTIVE_THRESHOLD <= 1.0):
        errors.append(f"EFFECTIVE_THRESHOLD deve essere in [0,1], trovato: {cfg.EFFECTIVE_THRESHOLD}")
    if cfg.RETENTION_DAYS < 0:
        errors.append(f"RETENTION_DAYS deve essere >= 0, trovato: {cfg.RETENTION_DAYS}")
    if errors:
        raise SystemExit("Config error:\n- " + "\n- ".join(errors))

def load_config() -> Config:
    cfg = Config()
    validate(cfg)
    return cfg
