"""
Transaction Cost Analysis (TCA) and Slippage Performance Attribution Engine.
Stage 30 — Modular, mathematically rigorous, auditable execution attribution layer.

Decomposes realized execution costs into:
1. Implementation Shortfall / Arrival Slippage:
   Signed slippage between decision arrival price and effective fill price.
2. Spread-Crossing Friction:
   Half quoted bid-ask spread cost on executed notional.
3. Non-Linear Temporary Market Impact:
   Instantaneous liquidity displacement (Barra/Almgren Square-Root Law or Kyle Linear).
4. Permanent Market Impact / Post-Trade Drift:
   Information leakage and structural price change.
5. Delay / Opportunity Cost:
   Adverse price movement on unexecuted, capped, or deferred order notional.
6. Execution Commissions & Exchange Fees:
   Brokerage and clearing friction.
7. Multi-Dimensional Attribution:
   Notional-weighted aggregation across market regimes (HMM states),
   execution scheduling modes (TWAP, VWAP, Almgren-Chriss, Single-Day),
   portfolio assets, and chronological rebalance events.

Accounting Invariant:
    Total Friction Cost = Spread Cost + Temp Impact + Perm Impact + Commission
    Residual Unattributed Cost = Total Observed Cost - Sum(Components) == 0.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal
import numpy as np


@dataclass
class TradeFill:
    """
    Represents an atomic execution tranche or fill for an asset.

    Attributes:
        date: Execution date string (YYYY-MM-DD).
        ticker: Asset identifier.
        direction: +1.0 for Buy, -1.0 for Sell.
        requested_notional: Intended trade notional in portfolio currency for this tranche.
        executed_notional: Actually executed trade notional in portfolio currency (>= 0).
        arrival_price: Reference price at decision time t (time t-1 close).
        fill_price: Effective realized execution price including trading friction.
        spread_cost: Cost of crossing half the bid-ask spread ($).
        temp_impact_cost: Modeled temporary market impact ($).
        perm_impact_cost: Modeled permanent market impact ($).
        commission_cost: Brokerage / exchange fees ($).
        total_cost: Total execution friction paid ($).
        realized_asset_return: Asset return on execution day t.
        regime_state: HMM state index at decision time (0 = calm, M-1 = turbulent).
        regime_p_turbulent: Belief probability of turbulent regime.
        scheduling_mode: Execution algorithm used ('single_day', 'twap', 'vwap', 'almgren_chriss', 'rejected', 'cancelled').
        scheduled_horizon_days: Planned execution window D.
        tranche_day_index: Index of tranche within schedule (0 .. D-1).
        parent_order_notional: Original total intended order notional across all tranches ($).
        order_id: Stable identifier linking tranches to parent rebalance order.
    """
    date: str
    ticker: str
    direction: float
    requested_notional: float
    executed_notional: float
    arrival_price: float
    fill_price: float
    spread_cost: float = 0.0
    temp_impact_cost: float = 0.0
    perm_impact_cost: float = 0.0
    commission_cost: float = 0.0
    total_cost: float = 0.0
    realized_asset_return: float = 0.0
    regime_state: int | None = None
    regime_p_turbulent: float = 0.0
    scheduling_mode: str = "single_day"
    scheduled_horizon_days: int = 1
    tranche_day_index: int = 0
    parent_order_notional: float = 0.0
    order_id: str = ""


def calculate_trade_slippage(
    direction: float,
    executed_notional: float,
    arrival_price: float,
    fill_price: float,
) -> dict[str, float]:
    """
    Computes signed arrival slippage (implementation shortfall).

    Convention:
        Adverse execution produces positive cost.
        Price improvement produces negative cost.

    Formula:
        Return diff = (fill_price - arrival_price) / arrival_price
        Signed Slippage ($) = direction * executed_notional * return_diff
        Slippage (bps) = 10^4 * signed_slippage / executed_notional

    Examples:
        - Buy (direction = +1): fill > arrival -> return_diff > 0 -> slippage > 0 (adverse)
        - Buy (direction = +1): fill < arrival -> return_diff < 0 -> slippage < 0 (improvement)
        - Sell (direction = -1): fill < arrival -> return_diff < 0 -> slippage > 0 (adverse)
        - Sell (direction = -1): fill > arrival -> return_diff > 0 -> slippage < 0 (improvement)
    """
    if executed_notional <= 1e-9 or arrival_price <= 1e-12:
        return {
            "signed_slippage_dollars": 0.0,
            "signed_slippage_bps": 0.0,
            "price_delta": 0.0,
            "price_return": 0.0,
        }

    s = 1.0 if direction > 0 else -1.0
    price_delta = float(fill_price - arrival_price)
    price_return = float(price_delta / arrival_price)
    signed_dollars = float(s * executed_notional * price_return)
    signed_bps = float((signed_dollars / executed_notional) * 10000.0)

    return {
        "signed_slippage_dollars": signed_dollars,
        "signed_slippage_bps": signed_bps,
        "price_delta": price_delta,
        "price_return": price_return,
    }


def calculate_opportunity_cost(
    direction: float,
    requested_notional: float,
    executed_notional: float,
    realized_asset_return: float,
) -> dict[str, float]:
    """
    Calculates delay / opportunity cost on unexecuted or deferred order notional.

    If an order cannot be fully executed due to volume limits or cash constraints,
    the unexecuted quantity experiences market movement during the holding period:
    - For an unexecuted buy (direction = +1):
      If asset rises (return > 0), the portfolio missed gains -> opportunity cost > 0.
      If asset falls (return < 0), the portfolio avoided losses -> opportunity cost < 0.
    - For an unexecuted sell (direction = -1):
      If asset falls (return < 0), the unliquidated holding lost value -> opportunity cost > 0.
      If asset rises (return > 0), the unliquidated holding gained value -> opportunity cost < 0.

    Formula:
        unexecuted_notional = max(0, requested_notional - executed_notional)
        opportunity_dollars = direction * unexecuted_notional * realized_asset_return
    """
    req = abs(float(requested_notional))
    exec_n = abs(float(executed_notional))
    unexec_n = max(0.0, req - exec_n)

    if unexec_n <= 1e-6:
        return {
            "unexecuted_notional": 0.0,
            "opportunity_cost_dollars": 0.0,
            "opportunity_cost_bps": 0.0,
        }

    s = 1.0 if direction > 0 else -1.0
    opp_dollars = float(s * unexec_n * realized_asset_return)
    opp_bps = float((opp_dollars / unexec_n) * 10000.0)

    return {
        "unexecuted_notional": round(unexec_n, 2),
        "opportunity_cost_dollars": round(opp_dollars, 2),
        "opportunity_cost_bps": round(opp_bps, 2),
    }


def _aggregate_fills_subset(fills: list[TradeFill]) -> dict[str, Any]:
    """
    Helper computing notional-weighted cost metrics over a subset of fills.

    Decomposition Identity:
        Total Cost = Spread Cost + Temp Impact + Perm Impact + Commission
        Unattributed Residual = Total Cost - Sum(Components)
    Note:
        In this simulated environment, Total Cost is constructed as the sum of
        modeled friction components. The zero unattributed residual confirms
        mathematical consistency of the structural accounting identity.
    """
    if not fills:
        return {
            "fill_count": 0,
            "total_requested_notional": 0.0,
            "total_executed_notional": 0.0,
            "total_unexecuted_notional": 0.0,
            "total_cost": 0.0,
            "effective_bps": 0.0,
            "spread_cost": 0.0,
            "spread_bps": 0.0,
            "temporary_impact_cost": 0.0,
            "temporary_impact_bps": 0.0,
            "permanent_impact_cost": 0.0,
            "permanent_impact_bps": 0.0,
            "market_impact_cost": 0.0,
            "market_impact_bps": 0.0,
            "commission_cost": 0.0,
            "commission_bps": 0.0,
            "opportunity_cost": 0.0,
            "opportunity_bps": 0.0,
            "realized_slippage": 0.0,
            "realized_slippage_bps": 0.0,
            "unattributed_cost": 0.0,
            "fill_rate_pct": 100.0,
        }

    tot_req = sum(abs(f.requested_notional) for f in fills)
    tot_exec = sum(f.executed_notional for f in fills)
    tot_unexec = max(0.0, tot_req - tot_exec)

    tot_spread = sum(f.spread_cost for f in fills)
    tot_temp = sum(f.temp_impact_cost for f in fills)
    tot_perm = sum(f.perm_impact_cost for f in fills)
    tot_comm = sum(f.commission_cost for f in fills)
    tot_cost = sum(f.total_cost for f in fills)

    # Opportunity cost summation
    tot_opp = 0.0
    for f in fills:
        opp_res = calculate_opportunity_cost(
            direction=f.direction,
            requested_notional=f.requested_notional,
            executed_notional=f.executed_notional,
            realized_asset_return=f.realized_asset_return,
        )
        tot_opp += opp_res["opportunity_cost_dollars"]

    # Realized signed arrival slippage summation (DEF-42-04 integration)
    tot_slippage = 0.0
    for f in fills:
        slip_res = calculate_trade_slippage(
            direction=f.direction,
            executed_notional=f.executed_notional,
            arrival_price=f.arrival_price,
            fill_price=f.fill_price,
        )
        tot_slippage += slip_res["signed_slippage_dollars"]

    # Notional-weighted basis points
    eff_bps = (tot_cost / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    spr_bps = (tot_spread / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    tmp_bps = (tot_temp / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    prm_bps = (tot_perm / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    mkt_bps = ((tot_temp + tot_perm) / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    com_bps = (tot_comm / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0
    opp_bps = (tot_opp / tot_unexec * 10000.0) if tot_unexec > 1e-6 else 0.0
    slip_bps = (tot_slippage / tot_exec * 10000.0) if tot_exec > 1e-6 else 0.0

    sum_components = tot_spread + tot_temp + tot_perm + tot_comm
    unattributed = float(tot_cost - sum_components)
    fill_rate = float((tot_exec / tot_req * 100.0) if tot_req > 1e-6 else 100.0)

    return {
        "fill_count": len(fills),
        "total_requested_notional": round(float(tot_req), 2),
        "total_executed_notional": round(float(tot_exec), 2),
        "total_unexecuted_notional": round(float(tot_unexec), 2),
        "total_cost": round(float(tot_cost), 2),
        "effective_bps": round(float(eff_bps), 2),
        "spread_cost": round(float(tot_spread), 2),
        "spread_bps": round(float(spr_bps), 2),
        "temporary_impact_cost": round(float(tot_temp), 2),
        "temporary_impact_bps": round(float(tmp_bps), 2),
        "permanent_impact_cost": round(float(tot_perm), 2),
        "permanent_impact_bps": round(float(prm_bps), 2),
        "market_impact_cost": round(float(tot_temp + tot_perm), 2),
        "market_impact_bps": round(float(mkt_bps), 2),
        "commission_cost": round(float(tot_comm), 2),
        "commission_bps": round(float(com_bps), 2),
        "opportunity_cost": round(float(tot_opp), 2),
        "opportunity_bps": round(float(opp_bps), 2),
        "realized_slippage": round(float(tot_slippage), 2),
        "realized_slippage_bps": round(float(slip_bps), 2),
        "unattributed_cost": round(unattributed, 4),
        "fill_rate_pct": round(fill_rate, 2),
    }


def compute_transaction_cost_analysis(
    fills: list[TradeFill],
    initial_capital: float = 100_000.0,
    annualization_factor: int = 252,
) -> dict[str, Any]:
    """
    Executes comprehensive Transaction Cost Analysis (TCA) and performance attribution.

    Produces:
        1. Portfolio-level aggregate summary with exact component reconciliation.
        2. Breakdown by market regime (calm vs turbulent).
        3. Breakdown by execution scheduling mode.
        4. Breakdown by asset ticker.
        5. Chronological event-level audit trail.
        6. Provenance metadata distinguishing observed vs modeled metrics.

    Args:
        fills: List of recorded TradeFill instances across the walk-forward simulation.
        initial_capital: Initial portfolio equity for reference drag calculation.
        annualization_factor: Business days per year (default 252).

    Returns:
        Structured TCA dictionary matching the Stage 30 data contract.
    """
    if not fills:
        empty_summary = _aggregate_fills_subset([])
        return {
            "summary": empty_summary,
            "by_regime": {},
            "by_mode": {},
            "by_asset": {},
            "by_event": [],
            "provenance": {
                "observed_components": ["total_traded_notional", "commission_cost", "fill_rate_pct"],
                "modeled_components": ["spread_cost", "temporary_impact_cost", "permanent_impact_cost"],
                "opportunity_cost_status": "modeled_daily_drift",
                "intraday_vwap_status": "unavailable_daily_bars",
                "currency_basis": "USD",
                "decomposition_type": "structural_modeled_identity",
                "permanent_impact_status": "not_modeled_zero",
                "reconciliation_status": "exact_modeled_identity_verified",
            },
        }

    # 1. Overall Portfolio Aggregate Summary
    summary = _aggregate_fills_subset(fills)
    summary["friction_drag_on_capital_pct"] = round(
        (summary["total_cost"] / initial_capital * 100.0) if initial_capital > 0 else 0.0, 4
    )

    # 2. Attribution by Market Regime
    by_regime: dict[str, Any] = {}
    regime_groups: dict[str, list[TradeFill]] = {}
    for f in fills:
        if f.regime_state is not None:
            lbl = f"State {f.regime_state}" + (" (Calm)" if f.regime_state == 0 else " (Turbulent)")
        else:
            lbl = "Unspecified / Disabled"
        regime_groups.setdefault(lbl, []).append(f)

    for r_lbl, r_fills in sorted(regime_groups.items()):
        by_regime[r_lbl] = _aggregate_fills_subset(r_fills)

    # 3. Attribution by Execution Scheduling Mode
    by_mode: dict[str, Any] = {}
    mode_groups: dict[str, list[TradeFill]] = {}
    for f in fills:
        mode_groups.setdefault(f.scheduling_mode, []).append(f)

    for m_lbl, m_fills in sorted(mode_groups.items()):
        by_mode[m_lbl] = _aggregate_fills_subset(m_fills)

    # 4. Attribution by Asset Ticker
    by_asset: dict[str, Any] = {}
    asset_groups: dict[str, list[TradeFill]] = {}
    for f in fills:
        asset_groups.setdefault(f.ticker, []).append(f)

    for t_lbl, t_fills in sorted(asset_groups.items()):
        by_asset[t_lbl] = _aggregate_fills_subset(t_fills)

    # 5. Chronological Event-Level Breakdown
    event_groups: dict[str, list[TradeFill]] = {}
    for f in fills:
        event_groups.setdefault(f.date, []).append(f)

    by_event: list[dict[str, Any]] = []
    for d_lbl, d_fills in sorted(event_groups.items()):
        event_agg = _aggregate_fills_subset(d_fills)
        # Dominant regime and mode for the event
        first_f = d_fills[0]
        event_agg["date"] = d_lbl
        event_agg["regime_state"] = first_f.regime_state
        event_agg["scheduling_mode"] = first_f.scheduling_mode
        event_agg["scheduled_horizon_days"] = first_f.scheduled_horizon_days
        by_event.append(event_agg)

    # 6. Provenance and Metadata (DEF-42-03)
    provenance = {
        "observed_components": ["total_traded_notional", "commission_cost", "fill_rate_pct"],
        "modeled_components": ["spread_cost", "temporary_impact_cost", "permanent_impact_cost"],
        "opportunity_cost_status": "modeled_daily_drift",
        "intraday_vwap_status": "unavailable_daily_bars",
        "currency_basis": "USD",
        "decomposition_type": "structural_modeled_identity",
        "permanent_impact_status": "modeled_linear_adv_ratio" if summary["permanent_impact_cost"] > 0 else "not_modeled_zero",
        "reconciliation_status": "exact_modeled_identity_verified" if abs(summary["unattributed_cost"]) < 1e-4 else "residual_warning",
    }

    return {
        "summary": summary,
        "by_regime": by_regime,
        "by_mode": by_mode,
        "by_asset": by_asset,
        "by_event": by_event,
        "provenance": provenance,
    }


def reconcile_tca_with_backtest_costs(
    tca_summary: dict[str, Any],
    backtest_total_costs: float,
    tolerance: float = 1e-4,
) -> bool:
    """
    Validates that the sum of TCA friction costs matches the total trading friction
    deducted by the backtest engine within numerical precision.
    """
    tca_tot = float(tca_summary.get("total_cost", 0.0))
    bt_tot = float(backtest_total_costs)
    diff = abs(tca_tot - bt_tot)
    return diff <= tolerance or (bt_tot > 0 and (diff / bt_tot) <= 1e-4)
