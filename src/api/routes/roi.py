from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException

from core.config import get_settings
from core.logging import get_logger
from analytics.roi import (
    load_roi_summary,
    load_roi_ledger,
    load_roi_timeline_raw,
    load_roi_daily,
)

logger = get_logger("api.routes.roi")

router = APIRouter(prefix="/roi", tags=["roi"])


@router.get("", summary="ROI summary e (opz.) picks ledger")
def roi_summary(
    detail: bool = Query(False, description="Se true include elenco picks (limit filtrato)"),
    source: Optional[List[str]] = Query(
        default=None,
        description="Filtra picks per source (prediction, consensus, merged) - parametro ripetibile",
    ),
    open_only: bool = Query(False, description="Mostra solo picks aperte (se detail=true)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limite picks in elenco"),
):
    settings = get_settings()
    if not settings.enable_roi_tracking:
        return {
            "enabled": False,
            "detail": False,
            "metrics": None,
            "items": [],
            "filters": {},
            "detail_included": False,
        }

    metrics = load_roi_summary()
    if not metrics:
        return {
            "enabled": True,
            "detail": False,
            "metrics": None,
            "items": [],
            "filters": {},
            "detail_included": False,
            "message": "metrics not available yet",
        }

    items = []
    detail_included = False
    chosen_sources = [s.lower() for s in source] if source else None

    if detail:
        ledger = load_roi_ledger()
        filtered = ledger
        if chosen_sources:
            filtered = [p for p in filtered if str(p.get("source")).lower() in chosen_sources]
        if open_only:
            filtered = [p for p in filtered if p.get("settled") is False]
        filtered.sort(key=lambda p: p.get("created_at") or "")
        if limit is not None:
            filtered = filtered[:limit]
        items = filtered
        detail_included = True

    return {
        "enabled": True,
        "detail": detail,
        "metrics": metrics,
        "items": items,
        "filters": {
            "sources": chosen_sources or [],
            "open_only": open_only,
            "limit": limit,
        },
        "detail_included": detail_included,
    }


@router.get("/timeline", summary="Timeline ROI e/o daily aggregate")
def roi_timeline(
    limit: int = Query(200, ge=1, le=2000, description="Numero massimo di record timeline (più recenti)"),
    start_date: Optional[str] = Query(None, description="Filtro ISO date (YYYY-MM-DD) ts >= start_date"),
    end_date: Optional[str] = Query(None, description="Filtro ISO date (YYYY-MM-DD) ts <= end_date"),
    mode: str = Query("both", pattern="^(full|daily|both)$", description="full=solo timeline, daily=solo daily, both=entrambi"),
):
    settings = get_settings()
    if not settings.enable_roi_tracking or not settings.enable_roi_timeline:
        return {
            "enabled": False,
            "mode": mode,
            "items": [],
            "count": 0,
            "daily": {},
            "filters": {},
        }

    def _parse_date(d: Optional[str]) -> Optional[datetime]:
        if not d:
            return None
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {d}. Expected YYYY-MM-DD")

    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if sd and ed and sd > ed:
        raise HTTPException(status_code=400, detail="start_date > end_date")

    items = []
    daily = {}

    include_full = mode in {"full", "both"}
    include_daily = mode in {"daily", "both"}

    if include_full:
        raw = load_roi_timeline_raw()

        def _ts(r: dict) -> str:
            return str(r.get("ts") or "")

        raw.sort(key=_ts)
        filtered: List[dict] = []
        for r in raw:
            ts = r.get("ts")
            if not ts:
                continue
            day_str = ts[:10]
            try:
                d_obj = datetime.strptime(day_str, "%Y-%m-%d")
            except Exception:
                continue
            if sd and d_obj < sd:
                continue
            if ed and d_obj > ed:
                continue
            filtered.append(r)
        if len(filtered) > limit:
            filtered = filtered[-limit:]
        items = filtered

    if include_daily:
        daily = load_roi_daily()
        if (sd or ed) and daily:
            d_filtered = {}
            for day_key, val in daily.items():
                try:
                    d_obj = datetime.strptime(day_key, "%Y-%m-%d")
                except Exception:
                    continue
                if sd and d_obj < sd:
                    continue
                if ed and d_obj > ed:
                    continue
                d_filtered[day_key] = val
            daily = d_filtered

    return {
        "enabled": True,
        "mode": mode,
        "count": len(items),
        "items": items,
        "daily": daily,
        "filters": {
            "limit": limit,
            "start_date": start_date,
            "end_date": end_date,
        },
        "included": {
            "timeline": include_full,
            "daily": include_daily,
        },
    }


@router.get("/analytics", summary="Dettagli analitici avanzati (Batch 37 + Batch 38)")
def roi_analytics():
    settings = get_settings()
    empty = {
        "enabled": False,
        "rolling": {},
        "rolling_multi": {},
        "hit_rate_multi": {},
        "clv": {},
        "risk": {},
        "anomalies": {},
        "stake_breakdown": {},
        "source_breakdown": {},
        "source_efficiency": {},
        "latency": {},
        "edge_deciles": [],
        "edge_buckets": [],
        "league_breakdown": [],
        "time_buckets": {},
        "side_breakdown": {},
        "clv_buckets": [],
        "aging_buckets": {},
        "edge_clv_corr": {},
        "stake_advisory": {},
        "profit_distribution": {},
        "risk_of_ruin_approx": None,
        "profit_per_pick": 0.0,
        "profit_per_unit_staked": 0.0,
        # Batch 38:
        "kelly_effectiveness": {},
        "payout_moments": {},
        "market_placeholder": {},
        "archive_stats": {},
        "montecarlo": {},
        "profit_buckets": [],
        "metrics_version": None,
    }
    if not settings.enable_roi_tracking:
        return empty

    metrics = load_roi_summary()
    if not metrics:
        empty["enabled"] = True
        return empty

    rolling_single = {
        "window_size": metrics.get("rolling_window_size"),
        "picks": metrics.get("picks_rolling"),
        "profit_units": metrics.get("profit_units_rolling"),
        "yield": metrics.get("yield_rolling"),
        "hit_rate": metrics.get("hit_rate_rolling"),
        "peak_profit": metrics.get("peak_profit_rolling"),
        "max_drawdown": metrics.get("max_drawdown_rolling"),
    }
    rolling_multi = metrics.get("rolling_multi") or {}
    return {
        "enabled": True,
        "metrics_version": metrics.get("metrics_version"),
        "rolling": rolling_single,
        "rolling_multi": rolling_multi,
        "hit_rate_multi": metrics.get("hit_rate_multi") or {},
        "clv": metrics.get("clv") or {},
        "risk": metrics.get("risk") or {},
        "anomalies": metrics.get("anomalies") or {},
        "stake_breakdown": metrics.get("stake_breakdown") or {},
        "source_breakdown": metrics.get("source_breakdown") or {},
        "source_efficiency": metrics.get("source_efficiency") or {},
        "latency": metrics.get("latency") or {},
        "edge_deciles": metrics.get("edge_deciles") or [],
        "edge_buckets": metrics.get("edge_buckets") or [],
        "league_breakdown": metrics.get("league_breakdown") or [],
        "time_buckets": metrics.get("time_buckets") or {},
        "side_breakdown": metrics.get("side_breakdown") or {},
        "clv_buckets": metrics.get("clv_buckets") or [],
        "aging_buckets": metrics.get("aging_buckets") or {},
        "edge_clv_corr": metrics.get("edge_clv_corr") or {},
        "stake_advisory": metrics.get("stake_advisory") or {},
        "profit_distribution": metrics.get("profit_distribution") or {},
        "risk_of_ruin_approx": metrics.get("risk_of_ruin_approx"),
        "profit_per_pick": metrics.get("profit_per_pick"),
        "profit_per_unit_staked": metrics.get("profit_per_unit_staked"),
        # Batch 38 additions
        "kelly_effectiveness": metrics.get("kelly_effectiveness") or {},
        "payout_moments": metrics.get("payout_moments") or {},
        "market_placeholder": metrics.get("market_placeholder") or {},
        "archive_stats": metrics.get("archive_stats") or {},
        "montecarlo": metrics.get("montecarlo") or {},
        "profit_buckets": metrics.get("profit_buckets") or [],
    }
