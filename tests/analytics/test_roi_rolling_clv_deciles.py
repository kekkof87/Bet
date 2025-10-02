import json
from pathlib import Path
import pytest
from analytics.roi import save_ledger, compute_metrics
from core.config import _reset_settings_cache_for_tests, get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_FOOTBALL_KEY", "DUMMY")
    monkeypatch.setenv("BET_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ROI_ROLLING_WINDOW", "5")
    monkeypatch.setenv("ENABLE_ROI_EDGE_DECILES", "1")
    monkeypatch.setenv("ENABLE_ROI_CLV_AGGREGATE", "1")
    _reset_settings_cache_for_tests()
    yield
    _reset_settings_cache_for_tests()


def _mk_pick(fid: int, created: str, result: str, stake: float, dec_odds: float, edge: float, clv: float):
    pick = {
        "created_at": created,
        "fixture_id": fid,
        "source": "prediction",
        "side": "home_win",
        "stake": stake,
        "decimal_odds": dec_odds,
        "edge": edge,
        "settled": True,
        "result": result,
    }
    if result == "win":
        pick["payout"] = round(dec_odds * stake, 6)
    else:
        pick["payout"] = 0.0
    pick["clv_pct"] = clv
    pick["settled_at"] = created
    return pick


def test_rolling_clv_deciles(tmp_path: Path):
    settings = get_settings()
    roi_dir = Path(settings.bet_data_dir) / settings.roi_dir
    roi_dir.mkdir(parents=True, exist_ok=True)

    # 8 picks (rolling window=5 -> ultimi 5)
    ledger = [
        _mk_pick(1, "2025-10-01T10:00:00Z", "win", 1, 2.0, 0.05, 0.02),
        _mk_pick(2, "2025-10-01T11:00:00Z", "loss", 1, 2.1, 0.06, -0.01),
        _mk_pick(3, "2025-10-01T12:00:00Z", "win", 1, 2.2, 0.07, 0.01),
        _mk_pick(4, "2025-10-01T13:00:00Z", "loss", 1, 1.9, 0.08, -0.02),
        _mk_pick(5, "2025-10-01T14:00:00Z", "win", 1, 2.5, 0.09, 0.03),
        _mk_pick(6, "2025-10-01T15:00:00Z", "loss", 1, 2.3, 0.10, -0.05),
        _mk_pick(7, "2025-10-01T16:00:00Z", "win", 1, 2.4, 0.11, 0.04),
        _mk_pick(8, "2025-10-01T17:00:00Z", "win", 1, 2.6, 0.12, 0.06),
    ]
    save_ledger(roi_dir, ledger)
    metrics = compute_metrics(ledger)

    assert metrics["rolling_window_size"] == 5
    assert metrics["picks_rolling"] == 5  # ultimi 5 pick
    # CLV aggregate
    assert metrics["avg_clv_pct"] is not None
    assert metrics["median_clv_pct"] is not None
    # Edge deciles presence
    assert isinstance(metrics["edge_deciles"], list)
    assert len(metrics["edge_deciles"]) >= 1
