"""
Exposure and baseline calculator for trade routes.
Deterministic calculations: baseline, post-event, percentage change, and divergence.
"""

from __future__ import annotations

from typing import Any
from src.core.schemas import TradeRow


def compute_route_baseline(
    rows: list[TradeRow],
    baseline_months: tuple[str, ...] = ("2026-07", "2026-08"),
) -> dict[str, float]:
    """
    Compute average monthly value and volume over the baseline period (pre-disruption).
    """
    baseline_rows = [r for r in rows if r.month in baseline_months]
    if not baseline_rows:
        return {"avg_value_usd_m": 0.0, "avg_volume_tonnes": 0.0}

    avg_val = sum(r.value_usd_m for r in baseline_rows) / len(baseline_rows)
    avg_vol = sum(r.volume_tonnes for r in baseline_rows) / len(baseline_rows)
    return {
        "avg_value_usd_m": round(avg_val, 2),
        "avg_volume_tonnes": round(avg_vol, 2),
    }


def compute_route_post_event(
    rows: list[TradeRow],
    post_months: tuple[str, ...] = ("2026-09", "2026-10", "2026-11", "2026-12"),
) -> dict[str, float]:
    """
    Compute average monthly value and volume over the post-event disruption period.
    """
    post_rows = [r for r in rows if r.month in post_months]
    if not post_rows:
        return {"avg_value_usd_m": 0.0, "avg_volume_tonnes": 0.0}

    avg_val = sum(r.value_usd_m for r in post_rows) / len(post_rows)
    avg_vol = sum(r.volume_tonnes for r in post_rows) / len(post_rows)
    return {
        "avg_value_usd_m": round(avg_val, 2),
        "avg_volume_tonnes": round(avg_vol, 2),
    }


def compute_route_exposure(
    rows: list[TradeRow],
    baseline_months: tuple[str, ...] = ("2026-07", "2026-08"),
    post_months: tuple[str, ...] = ("2026-09", "2026-10", "2026-11", "2026-12"),
) -> dict[str, Any]:
    """
    Compute full exposure metrics for a trade route:
    - Baseline average value & volume
    - Post-event average value & volume
    - Percentage drop in value and volume
    - Worst single-month drop (Thor's parameter)
    - Value vs Volume divergence (Loki's parameter)
    """
    base = compute_route_baseline(rows, baseline_months)
    post = compute_route_post_event(rows, post_months)

    val_change_pct = 0.0
    if base["avg_value_usd_m"] > 0:
        val_change_pct = round(
            ((post["avg_value_usd_m"] - base["avg_value_usd_m"]) / base["avg_value_usd_m"]) * 100,
            1,
        )

    vol_change_pct = 0.0
    if base["avg_volume_tonnes"] > 0:
        vol_change_pct = round(
            ((post["avg_volume_tonnes"] - base["avg_volume_tonnes"]) / base["avg_volume_tonnes"]) * 100,
            1,
        )

    # Worst single month drop compared to baseline
    worst_month = None
    worst_val_drop = 0.0
    for r in [x for x in rows if x.month in post_months]:
        if base["avg_value_usd_m"] > 0:
            drop = ((r.value_usd_m - base["avg_value_usd_m"]) / base["avg_value_usd_m"]) * 100
            if drop < worst_val_drop:
                worst_val_drop = drop
                worst_month = r.month

    # Value vs volume divergence: if value held up better than volume (price spike cushion)
    divergence = round(val_change_pct - vol_change_pct, 1)

    return {
        "baseline": base,
        "post_event": post,
        "value_change_pct": val_change_pct,
        "volume_change_pct": vol_change_pct,
        "worst_month": worst_month,
        "worst_month_drop_pct": round(worst_val_drop, 1),
        "divergence_pct": divergence,
    }
