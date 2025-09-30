"""
Predictions package.

Contiene:
- features: estrazione feature basilari
- model: BaselineModel
- pipeline: orchestrazione salvataggio predictions

Espone BaselineModel e run_baseline_predictions, con import protetto
per evitare errori se qualche modulo interno manca temporaneamente.
"""
from .model import BaselineModel  # noqa: F401

try:  # pragma: no cover
    from .pipeline import run_baseline_predictions  # noqa: F401
except Exception:  # Import difensivo (es. file non ancora presente nel commit)
    def run_baseline_predictions(*args, **kwargs):  # type: ignore
        raise RuntimeError("pipeline non disponibile (file mancante?)")


__all__ = ["BaselineModel", "run_baseline_predictions"]
