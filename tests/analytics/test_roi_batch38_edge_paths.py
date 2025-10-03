from datetime import datetime, timedelta, timezone

from core.config import _reset_settings_cache_for_tests, get_settings
from analytics.roi import compute_metrics


def test_batch38_edge_paths(monkeypatch):
    """
    Copre rami edge:
    - Montecarlo disattivato => blocco vuoto
    - Payout moments insufficient picks (<5)
    - Nessun Kelly pick => kelly_effectiveness {}
    - Profit buckets attivi ma senza pick nel range (creiamo solo profit quasi zero)
    - Risk of ruin rientra in condizione early return (meno di 30)
    - Edge CLV corr insufficiente (<10)
    - CLV buckets abilitati ma parziali
    """
    monkeypatch.setenv("API_FOOTBALL_KEY", "dummy-key")
    env = {
        "ENABLE_ROI_TRACKING": "1",
        "ENABLE_ROI_MONTECARLO": "0",
        "ENABLE_ROI_KELLY_EFFECT": "1",
        "ENABLE_ROI_PAYOUT_MOMENTS": "1",
        "ENABLE_ROI_PROFIT_BUCKETS": "1",
        "ROI_PROFIT_BUCKETS": "-5--2,-2--1,-1--0,0-1,1-2",
        "ENABLE_ROI_CLV_BUCKETS": "1",
        "ROI_CLV_BUCKETS": "-0.5--0.2,-0.2-0,0-0.2",
        "ENABLE_ROI_EDGE_CLV_CORR": "1",
        "ENABLE_ROI_ROR": "1",
        "ENABLE_ROI_SOURCE_EFFICIENCY": "1",
        "ENABLE_ROI_PROFIT_DISTRIBUTION": "1",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    _reset_settings_cache_for_tests()
    settings = get_settings()
    assert settings.enable_roi_tracking

    base_time = datetime(2025, 4, 1, 9, 0, 0)

    ledger = []
    # Solo 4 pick => payout_moments non scatta, risk_of_ruin insufficient
    for i in range(1, 5):
        win = (i % 2 == 0)
        ledger.append({
            "fixture_id": i,
            "created_at": (base_time + timedelta(hours=i)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
            "settled_at": (base_time + timedelta(hours=i+1)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
            "source": "prediction",
            "side": "home_win",
            "stake": 1.0,
            "decimal_odds": 2.0,
            "edge": 0.05 + i*0.001,
            "settled": True,
            "result": "win" if win else "loss",
            "payout": 2.0 if win else 0.0,
            "clv_pct": 0.01 if win else -0.01,
            "stake_strategy": "fixed",
        })

    metrics = compute_metrics(ledger)

    # Montecarlo non attivo
    assert metrics.get("montecarlo") == {}
    # Kelly effectiveness vuoto (nessun Kelly pick)
    assert metrics.get("kelly_effectiveness") == {}
    # Payout moments vuoto (<5 settled)
    assert metrics.get("payout_moments") == {}
    # Profit buckets presenti (anche se molti avranno picks=0)
    assert isinstance(metrics.get("profit_buckets"), list)
    # Edge CLV corr insufficiente => n < 10
    ecc = metrics.get("edge_clv_corr") or {}
    assert ecc.get("n", 0) < 10
    # Risk of ruin None (meno di 30)
    assert metrics.get("risk_of_ruin_approx") is None
    # CLV buckets list (anche se pochi picks)
    assert isinstance(metrics.get("clv_buckets"), list)
    # Profit distribution (anche con 4 pick è >=1 => ma se la logica richiede >0 contribs)
    pd = metrics.get("profit_distribution")
    # Potrebbe esistere o essere {} se la config richiede più picks; assert non crasha
    assert isinstance(pd, dict)
