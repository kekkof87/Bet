import os
from datetime import datetime, timedelta, timezone

from core.config import _reset_settings_cache_for_tests, get_settings
from analytics.roi import compute_metrics


def _mk_pick(
    idx: int,
    created_at: datetime,
    settle_after_days: int,
    source: str,
    side: str,
    stake: float,
    decimal_odds: float,
    edge: float,
    result: str,
    clv_pct: float,
) -> dict:
    """
    Crea un pick già “settled” con i campi richiesti per esercitare i rami:
      - edge
      - clv_pct
      - payout calcolato per win
    """
    settled_at = created_at + timedelta(days=settle_after_days)
    if result == "win":
        payout = round(decimal_odds * stake, 6)
    else:
        payout = 0.0
    return {
        "created_at": created_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "fixture_id": idx,
        "source": source,
        "side": side,
        "stake": stake,
        "decimal_odds": decimal_odds,
        "edge": edge,
        "settled": True,
        "result": result,
        "payout": payout,
        "clv_pct": clv_pct,
        "settled_at": settled_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def test_batch37_extended_metrics(monkeypatch):
    # Attiva tutti i flag core+plus introdotti in Batch 37
    env_flags = {
        "ENABLE_ROI_TRACKING": "1",
        "ENABLE_ROI_EQUITY_VOL": "1",
        "ROI_EQUITY_VOL_WINDOWS": "30,100",
        "ENABLE_ROI_ANOMALY_FLAGS": "1",
        "ENABLE_ROI_PROFIT_DISTRIBUTION": "1",
        "ENABLE_ROI_ROR": "1",
        "ENABLE_ROI_SOURCE_EFFICIENCY": "1",
        "ENABLE_ROI_EDGE_CLV_CORR": "1",
        "ENABLE_ROI_STAKE_ADVISORY": "1",
        "ROI_STAKE_ADVISORY_DD_PCT": "0.25",
        "ENABLE_ROI_AGING_BUCKETS": "1",
        "ROI_AGING_BUCKETS": "1,2,3,5",
        "ENABLE_ROI_SIDE_BREAKDOWN": "1",
        "ENABLE_ROI_CLV_BUCKETS": "1",
        "ROI_CLV_BUCKETS": "-0.1--0.05,-0.05-0,0-0.05,0.05-0.1,0.1-",
        # Garantiamo rolling windows default
        "ROI_ROLLING_WINDOWS": "7,30,90",
        # Evitiamo pruning
        "ROI_LEDGER_MAX_PICKS": "0",
        "ROI_LEDGER_MAX_AGE_DAYS": "0",
    }
    for k, v in env_flags.items():
        monkeypatch.setenv(k, v)

    # Reset cache settings per prendere i nuovi flag
    _reset_settings_cache_for_tests()
    settings = get_settings()
    assert settings.enable_roi_tracking

    # Costruiamo un ledger con > 40 picks per:
    # - risk_of_ruin (>=30)
    # - edge_clv_corr (>=10)
    # - aging buckets (varie differenze di giorni)
    # - drawdown (creiamo prima una salita forte poi una discesa)
    base_time = datetime(2025, 1, 1, 10, 0, 0)
    ledger = []

    # Prima fase: 15 win grandi per creare un picco
    for i in range(1, 16):
        ledger.append(
            _mk_pick(
                idx=i,
                created_at=base_time + timedelta(hours=i),
                settle_after_days=1 if i % 3 else 2,  # differenze di aging
                source="prediction" if i % 2 else "consensus",
                side="home_win",
                stake=1.0,
                decimal_odds=2.2,
                edge=0.05 + i * 0.001,
                result="win",
                clv_pct=0.01 + (i * 0.001),
            )
        )

    # Seconda fase: 10 loss per generare drawdown
    for j in range(16, 26):
        ledger.append(
            _mk_pick(
                idx=j,
                created_at=base_time + timedelta(hours=j),
                settle_after_days=2 if j % 2 else 3,
                source="prediction" if j % 3 else "merged",
                side="away_win",
                stake=1.2,
                decimal_odds=2.0,
                edge=0.06 + (j * 0.001),
                result="loss",
                clv_pct=-0.02 + (j * 0.0005),
            )
        )

    # Terza fase: mix win/loss per completare >40 picks e variare edge/clv
    outcomes = ["win", "loss"]
    for k in range(26, 46):
        outcome = outcomes[k % 2]
        ledger.append(
            _mk_pick(
                idx=k,
                created_at=base_time + timedelta(hours=k),
                settle_after_days=1 + (k % 4),
                source="consensus" if k % 4 else "merged",
                side="draw" if k % 5 == 0 else "home_win",
                stake=1.0 + (k % 3) * 0.1,
                decimal_odds=1.9 + (k % 4) * 0.1,
                edge=0.04 + (k * 0.0008),
                result=outcome,
                clv_pct=(-0.05 + k * 0.001) if outcome == "loss" else (0.005 + k * 0.0007),
            )
        )

    # Compute metrics
    metrics = compute_metrics(ledger)

    # Verifiche chiavi nuove (non controlliamo valori numerici esatti, solo presenza / tipo)
    for key in [
        "risk",
        "profit_distribution",
        "risk_of_ruin_approx",
        "source_efficiency",
        "edge_clv_corr",
        "aging_buckets",
        "side_breakdown",
        "clv_buckets",
        "stake_advisory",
        "hit_rate_multi",
        "anomalies",
    ]:
        assert key in metrics, f"Missing key {key}"

    # Alcuni controlli di struttura
    assert isinstance(metrics["risk"], dict)
    assert isinstance(metrics["profit_distribution"], dict)
    assert isinstance(metrics["source_efficiency"], dict)
    assert isinstance(metrics["side_breakdown"], dict)
    assert isinstance(metrics["anomalies"], dict)

    # edge_clv_corr deve indicare n >=10
    ecc = metrics["edge_clv_corr"]
    assert "n" in ecc and ecc["n"] >= 10

    # aging buckets deve contenere le bucket dichiarate
    if settings.enable_roi_aging_buckets:
        for b in settings.roi_aging_buckets:
            assert str(b) in metrics["aging_buckets"]

    # stake advisory (dovrebbe attivarsi se il drawdown è significativo)
    if settings.enable_roi_stake_advisory:
        adv = metrics["stake_advisory"]
        # Non obblighiamo che sia sempre presente, ma se presente deve avere recommended_factor
        if adv:
            assert "recommended_factor" in adv

    # equity volatility (inserita in risk.equity_vol)
    eq_vol = metrics["risk"].get("equity_vol", {})
    if settings.enable_roi_equity_vol:
        assert isinstance(eq_vol, dict)
        # almeno una finestra (es. w30)
        assert any(k.startswith("w") for k in eq_vol.keys()), "Missing equity vol windows"

    # Profit distribution percentili base se attivo
    if settings.enable_roi_profit_distribution:
        for k in ("p10", "median", "p90"):
            assert k in metrics["profit_distribution"]

    # CLV buckets se abilitati
    if settings.enable_roi_clv_buckets:
        assert isinstance(metrics["clv_buckets"], list)

    # Source efficiency se attivo
    if settings.enable_roi_source_efficiency:
        # almeno una fonte presente
        assert len(metrics["source_efficiency"]) >= 1

    # Anomalies: tutte le chiavi booleane
    if settings.enable_roi_anomaly_flags:
        for k in ("drawdown_alert", "yield_drop_alert", "vol_spike_alert"):
            assert k in metrics["anomalies"]

    # Risk of ruin se attivo (può essere None se edge negativo, ma chiave deve esserci)
    if settings.enable_roi_ror:
        assert "risk_of_ruin_approx" in metrics
