from __future__ import annotations

from typing import Dict, Any, Optional
from core.config import get_settings


def compute_value_block(
    model_prob: Dict[str, float],
    odds_implied: Dict[str, float],
    odds_margin: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Calcola value semplice:
    delta esito = p_model - p_implied
    value_side = esito con delta max (se >= threshold)
    value_edge = delta max
    """
    settings = get_settings()
    if not settings.enable_value_detection:
        return None

    keys = ["home_win", "draw", "away_win"]
    deltas: Dict[str, float] = {}
    for k in keys:
        pm = float(model_prob.get(k, 0.0))
        pi = float(odds_implied.get(k, 0.0))
        deltas[k] = pm - pi

    # trova max
    value_side = max(deltas, key=lambda k: deltas[k])
    value_edge = deltas[value_side]

    if value_edge < settings.value_min_edge:
        return {
            "active": False,
            "value_side": value_side,
            "value_edge": round(value_edge, 6),
            "deltas": {k: round(v, 6) for k, v in deltas.items()},
        }

    block: Dict[str, Any] = {
        "active": True,
        "value_side": value_side,
        "value_edge": round(value_edge, 6),
        "deltas": {k: round(v, 6) for k, v in deltas.items()},
    }

    if settings.value_include_adjusted and odds_margin is not None:
        block["adjusted_edge"] = round(value_edge * (1 + odds_margin), 6)

    return block
