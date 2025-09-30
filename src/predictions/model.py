from __future__ import annotations

from typing import Dict, List


class BaselineModel:
    """
    Modello baseline molto semplice:
    - Punto di partenza: home=0.33, draw=0.33, away=0.34
    - Aggiusta home/away in base a score_diff (0.05 * diff) limitato
    - Ricalibra per mantenere somma = 1 con draw come residuo
    - Forza ogni prob >= 0.05 per draw e >= 0.05 per home/away (dopo clamp)
    """

    def __init__(self, version: str = "baseline-v1") -> None:
        self.version = version

    def predict(self, features: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        for ft in features:
            base_home = 0.33
            base_away = 0.34
            score_diff = ft.get("score_diff", 0)
            try:
                diff = float(score_diff)
            except Exception:
                diff = 0.0
            adjust = 0.05 * diff
            home = base_home + adjust
            away = base_away - adjust
            # clamp
            home = max(min(home, 0.7), 0.05)
            away = max(min(away, 0.7), 0.05)
            draw = 1.0 - home - away
            if draw < 0.05:
                # normalizza mantenendo proporzioni home/away e imponendo draw minimo
                deficit = 0.05 - draw
                scale = (home + away)
                if scale <= 0:
                    home, away, draw = 0.47, 0.48, 0.05
                else:
                    home_ratio = home / scale
                    away_ratio = away / scale
                    home = home - deficit * home_ratio
                    away = away - deficit * away_ratio
                    draw = 0.05
            # normalizzazione finale
            s = home + away + draw
            if s <= 0:
                home, draw, away = 0.33, 0.34, 0.33
                s = 1.0
            home /= s
            draw /= s
            away /= s

            home_r = round(home, 4)
            draw_r = round(draw, 4)
            away_r = round(1.0 - home_r - draw_r, 4)  # correzione somma

            out.append(
                {
                    "fixture_id": ft.get("fixture_id"),
                    "prob": {
                        "home_win": home_r,
                        "draw": draw_r,
                        "away_win": away_r,
                    },
                    "model_version": self.version,
                }
            )
        return out


__all__ = ["BaselineModel"]
