"""
Predictions package.

Contiene:
- features: estrazione feature basilari
- model: BaselineModel
- pipeline: orchestrazione salvataggio predictions

Esporta BaselineModel e run_baseline_predictions per uso esterno.
"""
from .model import BaselineModel  # noqa: F401
from .pipeline import run_baseline_predictions  # noqa: F401

__all__ = ["BaselineModel", "run_baseline_predictions"]
