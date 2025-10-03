from datetime import datetime, timedelta, timezone

from core.config import _reset_settings_cache_for_tests, get_settings
from analytics.roi import compute_metrics


def _mk_pick(
    idx: int,
    base_time: datetime,
    hours_offset: int,
    source: str,
    side: str,
    stake: float,
    decimal_odds: float,
    edge: float,
    result: str,
    clv_pct: float,
    kelly: bool = False,
) -> dict:
    created = base_time + timedelta(hours=hours_offset)
    settled = created + timedelta(days=1 + (idx % 3))
    payout = decimal_odds * stake if result == "win" else 0.0
    pick = {
        "fixture_id": idx,
        "created_at": created.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "settled_at": settled.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "side": side,
        "stake": stake,
        "decimal_odds": decimal_odds,
        "edge": edge,
        "settled": True,
        "result": result,
        "payout": round(payout, 6),
        "clv_pct": clv_pct,
        # Simula Kelly: se kelly==True, metti stake_strategy e frazioni
        "stake_strategy": "kelly" if kelly else "fixed",
        "kelly_fraction": 0.05 if kelly else None,
        "kelly_fraction_capped": 0.05 if kelly else None,
        "kelly_prob": 0.55 if kelly else None,
        "kelly_b": (decimal_odds - 1) if kelly else None,
        "league_id": 99 if idx % 5 else 77,
        "value_type": "value",
    }
    return pick


def test_batch38_full_features(monkeypatch):
    # Imposta tutte le variabili necessarie
    monkeypatch.setenv("API_FOOTBALL_KEY", "dummy-key")

    # Batch 38 flags ON
    flags = {
        "ENABLE_ROI_TRACKING": "1",
        "ENABLE_ROI_EQUITY_VOL": "1",
        "ENABLE_ROI_ANOMALY_FLAGS": "1",
        "ENABLE_ROI_PROFIT_DISTRIBUTION": "1",
        "ENABLE_ROI_ROR": "1",
        "ENABLE_ROI_SOURCE_EFFICIENCY": "1",
        "ENABLE_ROI_EDGE_CLV_CORR": "1",
        "ENABLE_ROI_STAKE_ADVISORY": "1",
        "ENABLE_ROI_AGING_BUCKETS": "1",
        "ROI_AGING_BUCKETS": "1,2,3,5",
        "ENABLE_ROI_SIDE_BREAKDOWN": "1",
        "ENABLE_ROI_CLV_BUCKETS": "1",
        "ROI_CLV_BUCKETS": "-0.1--0.05,-0.05-0,0-0.05,0.05-0.1,0.1-",
        # Batch 38:
        "ENABLE_ROI_KELLY_EFFECT": "1",
        "ENABLE_ROI_PAYOUT_MOMENTS": "1",
        "ENABLE_ROI_MARKET_PLACEHOLDER": "1",
        "ENABLE_ROI_PROFIT_BUCKETS": "1",
        "ROI_PROFIT_BUCKETS": "-2--1,-1--0.5,-0.5-0,0-0.5,0.5-1,1-",
        "ENABLE_ROI_MONTECARLO": "1",
        "ROI_MC_RUNS": "60",
        "ROI_MC_WINDOW": "80",
        "ENABLE_ROI_ARCHIVE_STATS": "1",
        "ENABLE_ROI_COMPACT_EXPORT": "1",
        # Resto utile
        "ENABLE_KELLY_STAKING": "1",
    }
    for k, v in flags.items():
        monkeypatch.setenv(k, v)

    _reset_settings_cache_for_tests()
    settings = get_settings()
    assert settings.enable_roi_tracking

    base_time = datetime(2025, 2, 1, 12, 0, 0)

    # Genera ledger: mix di fonti e esiti
    ledger = []
    # 20 pick kelly wins/loss
    for i in range(1, 21):
        res = "win" if i % 3 else "loss"
        ledger.append(
            _mk_pick(
                idx=i,
                base_time=base_time,
                hours_offset=i,
                source="prediction" if i % 2 else "consensus",
                side="home_win" if i % 4 else "draw",
                stake=1.0 + (i % 3) * 0.2,
                decimal_odds=1.8 + (i % 5) * 0.15,
                edge=0.04 + i * 0.0015,
                result=res,
                clv_pct=0.01 * (1 if res == "win" else -1) + (i * 0.0005),
                kelly=True,
            )
        )
    # 25 pick fixed
    for j in range(21, 46):
        res = "loss" if j % 4 else "win"
        ledger.append(
            _mk_pick(
                idx=j,
                base_time=base_time,
                hours_offset=j,
                source="merged" if j % 3 == 0 else "consensus",
                side="away_win" if j % 5 else "home_win",
                stake=1.5,
                decimal_odds=1.9 + (j % 4) * 0.1,
                edge=0.035 + j * 0.001,
                result=res,
                clv_pct=(-0.02 + j * 0.0004) if res == "loss" else (0.008 + j * 0.0003),
                kelly=False,
            )
        )

    metrics = compute_metrics(ledger)

    # Controlli blocchi Batch 38
    assert metrics.get("metrics_version") == "2.0"
    assert isinstance(metrics.get("kelly_effectiveness"), dict)
    assert isinstance(metrics.get("payout_moments"), dict)
    assert isinstance(metrics.get("market_placeholder"), dict)
    assert isinstance(metrics.get("profit_buckets"), list)
    assert isinstance(metrics.get("montecarlo"), dict)
    # Montecarlo percentili presenti
    mc = metrics["montecarlo"]
    if mc:
        assert "p95_final_equity" in mc
    # Kelly uplift (può anche essere negativo, basta che esista la chiave)
    ke = metrics["kelly_effectiveness"]
    if ke:
        assert "uplift_pct" in ke
    # Payout moments
    pm = metrics["payout_moments"]
    if pm:
        assert "stddev" in pm and "kurtosis_excess" in pm
    # Profit buckets
    pb = metrics["profit_buckets"]
    if pb:
        # range formattati correttamente
        assert all("range" in b for b in pb)
    # Archive stats (non abbiamo ledger_archive qui, può essere vuoto)
    assert "archive_stats" not in metrics or isinstance(metrics["archive_stats"], dict)

    # Market placeholder structure
    mp = metrics.get("market_placeholder") or {}
    if mp:
        assert "markets" in mp


def test_batch38_full_features_compact_export(monkeypatch, tmp_path):
    """
    Test separato che verifica solo la compact export (senza Montecarlo per velocità),
    controllando che il file sia serializzabile e coerente.
    """
    monkeypatch.setenv("API_FOOTBALL_KEY", "dummy-key")
    monkeypatch.setenv("ENABLE_ROI_TRACKING", "1")
    monkeypatch.setenv("ENABLE_ROI_COMPACT_EXPORT", "1")
    # Disabilito Montecarlo per non sporcare test rapidi
    monkeypatch.setenv("ENABLE_ROI_MONTECARLO", "0")

    from analytics.roi import compute_metrics, _compact_export  # import locale

    base_time = datetime(2025, 3, 1, 10, 0, 0)
    ledger = []
    for i in range(1, 6):
        ledger.append(
            {
                "fixture_id": i,
                "created_at": (base_time + timedelta(hours=i)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
                "settled_at": (base_time + timedelta(hours=i+2)).replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
                "source": "prediction",
                "side": "home_win",
                "stake": 1.0,
                "decimal_odds": 2.0,
                "edge": 0.06,
                "settled": True,
                "result": "win" if i % 2 else "loss",
                "payout": 2.0 if i % 2 else 0.0,
                "clv_pct": 0.01 * (1 if i % 2 else -1),
                "stake_strategy": "fixed",
            }
        )
    _reset_settings_cache_for_tests()
    metrics = compute_metrics(ledger)
    # Simula base /roi in tmp
    roi_dir = tmp_path / "roi"
    roi_dir.mkdir()
    _compact_export(roi_dir, metrics)
    compact_file = roi_dir / "roi_metrics_compact.json"
    content = compact_file.read_text(encoding="utf-8")
    assert '"profit_units"' in content
    assert '"metrics_version": "2.0"' in content
