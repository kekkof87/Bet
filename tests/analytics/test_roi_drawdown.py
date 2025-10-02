from pathlib import Path
import pytest

from analytics.roi import save_ledger, compute_metrics  # using internal functions via import path
from core.config import _reset_settings_cache_for_tests, get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def test_drawdown_metrics(tmp_path: Path):
    """
    Sequenza equity (profit cumulativo per pick settled):
      Pick1 win @2.0 stake1 -> +1   (equity 1)
      Pick2 loss stake1     -> -1   (equity 0)
      Pick3 win @3.0 stake1 -> +2   (equity 2)
      Pick4 loss stake1     -> -1   (equity 1)
    peak = 2
    max drawdown = max(1 (da 1 a 0), 1 (da 2 a 1)) = 1
    current drawdown = peak(2) - final(1) = 1
    """
    settings = get_settings()
    roi_dir = Path(settings.bet_data_dir) / settings.roi_dir
    roi_dir.mkdir(parents=True, exist_ok=True)

    ledger = [
        {
            "created_at": "2025-10-01T10:00:00Z",
            "fixture_id": 1,
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 2.0,
            "settled": True,
            "result": "win",
            "payout": 2.0,
        },
        {
            "created_at": "2025-10-01T11:00:00Z",
            "fixture_id": 2,
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 2.1,
            "settled": True,
            "result": "loss",
            "payout": 0.0,
        },
        {
            "created_at": "2025-10-01T12:00:00Z",
            "fixture_id": 3,
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 3.0,
            "settled": True,
            "result": "win",
            "payout": 3.0,
        },
        {
            "created_at": "2025-10-01T13:00:00Z",
            "fixture_id": 4,
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 2.2,
            "settled": True,
            "result": "loss",
            "payout": 0.0,
        },
    ]
    save_ledger(roi_dir, ledger)
    metrics = compute_metrics(ledger)
    assert metrics["profit_units"] == 1.0
    assert metrics["peak_profit"] == 2.0
    assert metrics["max_drawdown"] == 1.0
    assert metrics["current_drawdown"] == 1.0
    assert abs(metrics["max_drawdown_pct"] - 0.5) < 1e-9
    assert abs(metrics["current_drawdown_pct"] - 0.5) < 1e-9
    assert metrics["equity_points"] == 4
