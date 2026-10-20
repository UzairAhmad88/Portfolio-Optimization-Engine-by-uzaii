"""
Pure Numerical Financial Mathematics Core for Optimal Trade Execution,
Market Impact Modeling, and Algorithmic Trade Scheduling.

Implements:
1. Almgren-Chriss (2000) optimal execution framework balancing expected
   implementation shortfall against timing risk (price volatility).
2. Closed-form analytical trajectories: x_j^* = X_0 * sinh(kappa * (T - t_j)) / sinh(kappa * T).
3. Benchmark schedules: Pure TWAP (Time-Weighted Average Price) and VWAP (Volume-Weighted Average Price).
4. Square-Root Law of Market Impact (Barra / Almgren et al. 2005) for portfolio rebalancing.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np


def compute_almgren_chriss_trajectory(
    order_size: float,
    asset_price: float,
    daily_volume: float,
    daily_volatility: float,
    bid_ask_spread: float = 0.0,
    horizon_periods: int = 10,
    trading_hours: float = 6.5,
    risk_aversion: float = 1e-6,
    temporary_impact_factor: float | None = None,
    permanent_impact_factor: float | None = None,
    volume_profile: list[float] | None = None,
) -> dict[str, Any]:
    """
    Computes the optimal Almgren-Chriss execution trajectory along with TWAP and VWAP baselines.

    Args:
        order_size: Total number of shares to execute (X_0 > 0).
        asset_price: Initial spot arrival price (S_0 > 0).
        daily_volume: Average Daily Volume in shares (ADV > 0).
        daily_volatility: Daily volatility in price units or fractional return * price.
                          e.g. if daily return vol is 2% and price is $50, daily_volatility = $1.00.
        bid_ask_spread: Quoted bid-ask spread in currency units (Spread >= 0).
        horizon_periods: Number of discrete trading intervals N (>= 2).
        trading_hours: Total trading day duration in hours (e.g. 6.5 for US equity market).
        risk_aversion: Trader's risk aversion parameter lambda (>= 0).
        temporary_impact_factor: Parameter eta for temporary market impact.
                                 If None, calibrated as: 0.1 * daily_volatility / (0.1 * daily_volume).
        permanent_impact_factor: Parameter gamma for permanent market impact.
                                 If None, calibrated as: 0.1 * daily_volatility / daily_volume.
        volume_profile: Optional list of N volume fractions representing intraday volume distribution.

    Returns:
        dict containing schedule points, TWAP/VWAP benchmarks, and cost/variance summary metrics.
    """
    if order_size <= 0:
        raise ValueError(f"Order size ({order_size}) must be strictly positive.")
    if asset_price <= 0:
        raise ValueError(f"Asset price ({asset_price}) must be strictly positive.")
    if daily_volume <= 0:
        raise ValueError(f"Daily volume ({daily_volume}) must be strictly positive.")
    if daily_volatility <= 0:
        raise ValueError(f"Daily volatility ({daily_volatility}) must be strictly positive.")
    if horizon_periods < 2:
        raise ValueError(f"Horizon periods ({horizon_periods}) must be at least 2.")

    N = horizon_periods
    X0 = float(order_size)
    S0 = float(asset_price)
    sigma = float(daily_volatility)
    spread = max(0.0, float(bid_ask_spread))
    lam = max(0.0, float(risk_aversion))

    # Time discretization: total horizon T normalized to 1.0 day fraction
    # tau = T / N in units of trading days
    tau = 1.0 / N
    T = 1.0

    # Calibrate default market impact parameters if not provided
    # Standard Almgren et al. rule of thumb:
    # eta = (sigma / (0.1 * ADV)) * c_temp
    # gamma = (sigma / ADV) * c_perm
    if temporary_impact_factor is not None:
        eta = max(1e-12, float(temporary_impact_factor))
    else:
        eta = float((sigma / (0.10 * daily_volume)) * 0.5)

    if permanent_impact_factor is not None:
        gamma = max(0.0, float(permanent_impact_factor))
    else:
        gamma = float((sigma / daily_volume) * 0.1)

    # Calculate urgency parameter kappa
    # Continuous approx: kappa = sqrt(lambda * sigma^2 / eta)
    # Discrete exact: cosh(kappa * tau) = 1 + 0.5 * lambda * sigma^2 * tau^2 / eta
    arg = 1.0 + 0.5 * (lam * (sigma**2) * (tau**2)) / eta
    if arg < 1.0:
        arg = 1.0
    kappa_tau = math.acosh(arg)
    kappa = kappa_tau / tau

    # Half-life of execution: time to trade 50% of the order
    half_life_days = (math.log(2.0) / kappa) if kappa > 1e-8 else (0.5 * T)
    half_life_hours = half_life_days * trading_hours

    # Standard U-shaped intraday volume profile if not provided
    if volume_profile is None or len(volume_profile) != N:
        # Default U-shaped volume curve: higher at open/close, lower midday
        t_arr = np.linspace(-1.0, 1.0, N)
        u_curve = 0.5 + 0.5 * (t_arr**2)
        vol_weights = u_curve / np.sum(u_curve)
    else:
        vol_arr = np.asarray(volume_profile, dtype=np.float64)
        vol_weights = vol_arr / np.sum(vol_arr)

    # 1. Almgren-Chriss Optimal Trajectory
    # x_j is remaining shares at end of period j, for j = 0..N
    # x_0 = X_0, x_N = 0
    x_opt = np.zeros(N + 1, dtype=np.float64)
    x_opt[0] = X0

    if kappa_tau < 1e-6:
        # Risk-neutral limit (lambda -> 0): linear TWAP trajectory
        for j in range(1, N):
            t_j = j * tau
            x_opt[j] = X0 * (1.0 - t_j / T)
    else:
        sinh_kappa_T = math.sinh(kappa * T)
        for j in range(1, N):
            t_j = j * tau
            num = math.sinh(kappa * (T - t_j))
            x_opt[j] = X0 * (num / sinh_kappa_T)
    x_opt[N] = 0.0

    # Trade sizes n_k = x_{k-1} - x_k
    n_opt = np.diff(-x_opt)  # x_{k-1} - x_k
    n_opt = np.maximum(0.0, n_opt)
    # Ensure exact sum conservation
    if np.sum(n_opt) > 0:
        n_opt = n_opt * (X0 / np.sum(n_opt))

    # 2. TWAP Baseline Trajectory
    n_twap = np.full(N, X0 / N, dtype=np.float64)
    x_twap = np.zeros(N + 1, dtype=np.float64)
    x_twap[0] = X0
    for j in range(1, N + 1):
        x_twap[j] = x_twap[j - 1] - n_twap[j - 1]
    x_twap[N] = 0.0

    # 3. VWAP Baseline Trajectory
    n_vwap = X0 * vol_weights
    x_vwap = np.zeros(N + 1, dtype=np.float64)
    x_vwap[0] = X0
    for j in range(1, N + 1):
        x_vwap[j] = x_vwap[j - 1] - n_vwap[j - 1]
    x_vwap[N] = 0.0

    # 4. Implementation Shortfall & Risk Calculations
    # Expected Cost: E[I] = 0.5 * gamma * X0^2 + 0.5 * spread * X0 + (eta / tau) * sum(n_k^2)
    # Variance of Cost: V[I] = sigma^2 * tau * sum_{k=1}^N x_k^2
    def calc_cost_and_variance(n_trades: np.ndarray, x_holdings: np.ndarray) -> tuple[float, float, float]:
        cost_perm = 0.5 * gamma * (X0**2)
        cost_spread = 0.5 * spread * X0
        cost_temp = (eta / tau) * float(np.sum(n_trades**2))
        total_cost = cost_perm + cost_spread + cost_temp
        var_cost = (sigma**2) * tau * float(np.sum(x_holdings[1:] ** 2))
        utility = total_cost + lam * var_cost
        return total_cost, var_cost, utility

    opt_cost, opt_var, opt_utility = calc_cost_and_variance(n_opt, x_opt)
    twap_cost, twap_var, twap_utility = calc_cost_and_variance(n_twap, x_twap)
    vwap_cost, vwap_var, vwap_utility = calc_cost_and_variance(n_vwap, x_vwap)

    total_order_value = X0 * S0
    opt_cost_bps = (opt_cost / total_order_value) * 10000.0 if total_order_value > 0 else 0.0
    twap_cost_bps = (twap_cost / total_order_value) * 10000.0 if total_order_value > 0 else 0.0
    vwap_cost_bps = (vwap_cost / total_order_value) * 10000.0 if total_order_value > 0 else 0.0

    cost_savings_vs_twap = twap_utility - opt_utility
    cost_savings_bps = (cost_savings_vs_twap / total_order_value) * 10000.0 if total_order_value > 0 else 0.0

    # Build schedule points for visualization
    schedule_points: list[dict[str, Any]] = []
    for k in range(N):
        period_idx = k + 1
        time_elapsed_hours = (k + 1) * tau * trading_hours
        schedule_points.append({
            "period": period_idx,
            "time_elapsed_hours": round(time_elapsed_hours, 2),
            "time_elapsed_pct": round((k + 1) / N, 4),
            "almgren_chriss_shares": round(float(n_opt[k]), 2),
            "almgren_chriss_remaining": round(float(x_opt[k + 1]), 2),
            "twap_shares": round(float(n_twap[k]), 2),
            "twap_remaining": round(float(x_twap[k + 1]), 2),
            "vwap_shares": round(float(n_vwap[k]), 2),
            "vwap_remaining": round(float(x_vwap[k + 1]), 2),
            "volume_weight_pct": round(float(vol_weights[k] * 100.0), 2),
        })

    return {
        "parameters": {
            "order_size": X0,
            "asset_price": S0,
            "order_value": total_order_value,
            "daily_volume": daily_volume,
            "daily_volatility": sigma,
            "bid_ask_spread": spread,
            "horizon_periods": N,
            "trading_hours": trading_hours,
            "risk_aversion": lam,
            "temporary_impact_eta": eta,
            "permanent_impact_gamma": gamma,
        },
        "summary": {
            "urgency_parameter": round(kappa, 6),
            "half_life_hours": round(half_life_hours, 2),
            "expected_cost": round(opt_cost, 2),
            "expected_cost_bps": round(opt_cost_bps, 2),
            "timing_risk_variance": round(opt_var, 2),
            "timing_risk_std": round(math.sqrt(max(0.0, opt_var)), 2),
            "execution_utility": round(opt_utility, 2),
            "twap_expected_cost": round(twap_cost, 2),
            "twap_expected_cost_bps": round(twap_cost_bps, 2),
            "twap_timing_risk_std": round(math.sqrt(max(0.0, twap_var)), 2),
            "twap_utility": round(twap_utility, 2),
            "vwap_expected_cost": round(vwap_cost, 2),
            "vwap_expected_cost_bps": round(vwap_cost_bps, 2),
            "cost_savings_vs_twap": round(cost_savings_vs_twap, 2),
            "cost_savings_vs_twap_bps": round(cost_savings_bps, 2),
        },
        "schedule": schedule_points,
    }


def compute_rebalance_market_impact(
    traded_notionals: dict[str, float],
    adv_dict: dict[str, float],
    volatility_dict: dict[str, float],
    spread_bps_dict: dict[str, float] | None = None,
    execution_horizon_days: float = 1.0,
    impact_model: Literal["square_root", "linear", "fixed_bps"] = "square_root",
    c_temp: float = 0.5,
    c_perm: float = 0.1,
    fixed_bps_rate: float = 10.0,
    commission_bps: float = 0.0,
    max_participation_rate: float = 0.10,
    participation_policy: Literal["warn", "cap", "reject"] = "warn",
) -> dict[str, Any]:
    """
    Evaluates non-linear market impact, bid-ask spread friction, commissions,
    and volume participation limits across a multi-asset portfolio rebalance.

    Uses the institutional Barra / Almgren Square-Root Law:
        Spread Cost = Traded Notional * (Spread_bps * 1e-4 / 2)
        Temp Impact = Traded Notional * c_temp * Volatility * sqrt(min(Participation, Cap))
        Perm Impact = Traded Notional * c_perm * Volatility * (Traded Notional / ADV)
        Commission  = Traded Notional * (Commission_bps * 1e-4)
        Total Cost  = Spread Cost + Temp Impact + Perm Impact + Commission

    Args:
        traded_notionals: Dict mapping ticker to dollar value traded: |w_target - w_drift| * Equity.
        adv_dict: Dict mapping ticker to Average Daily Dollar Volume.
        volatility_dict: Dict mapping ticker to annualized asset return volatility (e.g. 0.20 for 20%).
        spread_bps_dict: Dict mapping ticker to quoted bid-ask spread in basis points (default 5 bps).
        execution_horizon_days: Time window allocated to execute the rebalance in days (>= 0.1).
        impact_model: 'square_root' (Barra/Almgren), 'linear' (Kyle model), or 'fixed_bps' (baseline).
        c_temp: Temporary market impact coefficient (empirical default: 0.5).
        c_perm: Permanent market impact coefficient (empirical default: 0.1).
        fixed_bps_rate: Fixed basis-point rate for 'fixed_bps' baseline comparison.
        commission_bps: Brokerage fee / commission in basis points.
        max_participation_rate: Configurable volume participation limit (e.g. 0.10 for 10% of ADV).
        participation_policy: Policy when participation exceeds limit: 'warn', 'cap', or 'reject'.

    Returns:
        dict containing per-asset impact breakdown, participation diagnostics, and aggregate statistics.
    """
    horizon = max(0.1, float(execution_horizon_days))
    spread_map = spread_bps_dict or {}

    total_traded = 0.0
    total_spread_cost = 0.0
    total_temp_cost = 0.0
    total_perm_cost = 0.0
    total_commission_cost = 0.0
    total_cost = 0.0

    asset_results: list[dict[str, Any]] = []
    max_participation_observed = 0.0
    participation_warnings_count = 0
    rebalance_rejected = False

    # Check for reject policy trigger across all trades first
    if participation_policy == "reject":
        for tkr, notional in traded_notionals.items():
            trade_val = max(0.0, float(notional))
            if trade_val <= 1e-6:
                continue
            adv = max(1000.0, float(adv_dict.get(tkr, 10_000_000.0)))
            pr = trade_val / (adv * horizon)
            if pr > max_participation_observed:
                max_participation_observed = pr
            if pr > max_participation_rate:
                rebalance_rejected = True
                participation_warnings_count += 1
                break

    if rebalance_rejected:
        return {
            "summary": {
                "impact_model": impact_model,
                "execution_horizon_days": horizon,
                "total_traded_notional": 0.0,
                "total_spread_cost": 0.0,
                "total_temporary_impact_cost": 0.0,
                "total_permanent_impact_cost": 0.0,
                "total_market_impact_cost": 0.0,
                "total_commission_cost": 0.0,
                "total_impact_cost": 0.0,
                "effective_cost_bps": 0.0,
                "max_participation_rate_observed": round(max_participation_observed, 4),
                "participation_warnings_count": participation_warnings_count,
                "rebalance_rejected": True,
            },
            "asset_impacts": [],
        }

    for tkr, notional in traded_notionals.items():
        trade_val = max(0.0, float(notional))
        if trade_val <= 1e-6:
            continue

        adv = max(1000.0, float(adv_dict.get(tkr, 10_000_000.0)))
        ann_vol = max(0.01, float(volatility_dict.get(tkr, 0.20)))
        daily_vol = ann_vol / math.sqrt(252.0)
        spread_bps = max(0.0, float(spread_map.get(tkr, 5.0)))

        # Participation rate: fraction of ADV represented by this trade
        raw_pr = trade_val / (adv * horizon)
        if raw_pr > max_participation_observed:
            max_participation_observed = raw_pr

        participation_warning = False
        trade_exec = trade_val

        if raw_pr > max_participation_rate:
            participation_warning = True
            participation_warnings_count += 1
            if participation_policy == "cap":
                # Cap the trade notional to the participation limit
                trade_exec = max_participation_rate * adv * horizon

        participation_rate = trade_exec / (adv * horizon)
        participation_pct = participation_rate * 100.0
        total_traded += trade_exec

        if impact_model == "square_root":
            # 1. Half bid-ask spread crossing cost
            cost_spread = trade_exec * (spread_bps * 1e-4 / 2.0)
            # 2. Temporary impact: proportional to daily_vol * sqrt(participation_rate)
            cost_temp = trade_exec * (c_temp * daily_vol * math.sqrt(min(participation_rate, 2.0)))
            # 3. Permanent impact: linear in participation rate
            cost_perm = trade_exec * (c_perm * daily_vol * min(trade_exec / adv, 1.0))
            # 4. Commission fee
            cost_fee = trade_exec * (commission_bps * 1e-4)
            asset_cost = cost_spread + cost_temp + cost_perm + cost_fee

        elif impact_model == "linear":
            cost_spread = trade_exec * (spread_bps * 1e-4 / 2.0)
            cost_temp = trade_exec * (c_temp * daily_vol * participation_rate)
            cost_perm = trade_exec * (c_perm * daily_vol * (trade_exec / adv))
            cost_fee = trade_exec * (commission_bps * 1e-4)
            asset_cost = cost_spread + cost_temp + cost_perm + cost_fee

        else:
            # fixed_bps baseline
            cost_spread = trade_exec * (fixed_bps_rate * 1e-4)
            cost_temp = 0.0
            cost_perm = 0.0
            cost_fee = 0.0
            asset_cost = cost_spread

        cost_bps = (asset_cost / trade_exec) * 10000.0 if trade_exec > 0 else 0.0

        total_spread_cost += cost_spread
        total_temp_cost += cost_temp
        total_perm_cost += cost_perm
        total_commission_cost += cost_fee
        total_cost += asset_cost

        asset_results.append({
            "ticker": tkr,
            "traded_notional": round(trade_val, 2),
            "executed_notional": round(trade_exec, 2),
            "adv": round(adv, 2),
            "participation_rate": round(participation_rate, 4),
            "participation_rate_pct": round(participation_pct, 2),
            "participation_warning": participation_warning,
            "spread_cost": round(cost_spread, 2),
            "temporary_impact_cost": round(cost_temp, 2),
            "permanent_impact_cost": round(cost_perm, 2),
            "market_impact_cost": round(cost_temp + cost_perm, 2),
            "commission_cost": round(cost_fee, 2),
            "total_cost": round(asset_cost, 2),
            "total_cost_bps": round(cost_bps, 2),
        })

    effective_bps = (total_cost / total_traded * 10000.0) if total_traded > 0 else 0.0
    total_market_impact = total_temp_cost + total_perm_cost

    return {
        "summary": {
            "impact_model": impact_model,
            "execution_horizon_days": horizon,
            "total_traded_notional": round(total_traded, 2),
            "total_spread_cost": round(total_spread_cost, 2),
            "total_temporary_impact_cost": round(total_temp_cost, 2),
            "total_permanent_impact_cost": round(total_perm_cost, 2),
            "total_market_impact_cost": round(total_market_impact, 2),
            "total_commission_cost": round(total_commission_cost, 2),
            "total_impact_cost": round(total_cost, 2),
            "effective_cost_bps": round(effective_bps, 2),
            "max_participation_rate_observed": round(max_participation_observed, 4),
            "participation_warnings_count": participation_warnings_count,
            "rebalance_rejected": False,
        },
        "asset_impacts": sorted(asset_results, key=lambda x: x["traded_notional"], reverse=True),
    }


def compute_liquidity_adjusted_var_cvar(
    weights: dict[str, float],
    portfolio_equity: float,
    adv_dict: dict[str, float],
    volatility_dict: dict[str, float],
    market_var: float,
    market_cvar: float,
    spread_bps_dict: dict[str, float] | None = None,
    execution_horizon_days: float = 1.0,
    impact_model: Literal["square_root", "linear", "fixed_bps"] = "square_root",
    c_temp: float = 0.5,
    c_perm: float = 0.1,
    fixed_bps_rate: float = 10.0,
    commission_bps: float = 0.0,
) -> dict[str, float]:
    """
    Computes Liquidity-Adjusted Value-at-Risk (L-VaR) and Conditional Value-at-Risk (L-CVaR)
    under an orderly liquidation unwind of the current portfolio positions.

    L-VaR  = Market_VaR  + Liquidation_Cost_Fraction
    L-CVaR = Market_CVaR + Liquidation_Cost_Fraction
    """
    if portfolio_equity <= 0:
        return {
            "market_var": float(market_var),
            "market_cvar": float(market_cvar),
            "liquidation_cost": 0.0,
            "liquidation_cost_bps": 0.0,
            "l_var": float(market_var),
            "l_cvar": float(market_cvar),
        }

    # Liquidation notionals: complete liquidation of all current positions
    liq_notionals = {tk: max(0.0, float(w)) * portfolio_equity for tk, w in weights.items()}
    liq_impact = compute_rebalance_market_impact(
        traded_notionals=liq_notionals,
        adv_dict=adv_dict,
        volatility_dict=volatility_dict,
        spread_bps_dict=spread_bps_dict,
        execution_horizon_days=execution_horizon_days,
        impact_model=impact_model,
        c_temp=c_temp,
        c_perm=c_perm,
        fixed_bps_rate=fixed_bps_rate,
        commission_bps=commission_bps,
        participation_policy="warn",
    )
    total_liq_cost = float(liq_impact["summary"]["total_impact_cost"])
    cost_frac = total_liq_cost / portfolio_equity if portfolio_equity > 0 else 0.0
    liq_bps = cost_frac * 10000.0

    return {
        "market_var": round(float(market_var), 4),
        "market_cvar": round(float(market_cvar), 4),
        "liquidation_cost": round(total_liq_cost, 2),
        "liquidation_cost_bps": round(liq_bps, 2),
        "l_var": round(float(market_var) + cost_frac, 4),
        "l_cvar": round(float(market_cvar) + cost_frac, 4),
    }


def compute_scenario_endogenous_liquidity_risk(
    weights: dict[str, float],
    portfolio_equity: float,
    adv_dict: dict[str, float],
    volatility_dict: dict[str, float],
    simulated_returns: np.ndarray,
    tickers: list[str],
    confidence_level: float = 0.99,
    spread_bps_dict: dict[str, float] | None = None,
    execution_horizon_days: float = 1.0,
    impact_model: Literal["square_root", "linear", "fixed_bps"] = "square_root",
    c_temp: float = 0.5,
    c_perm: float = 0.1,
    fixed_bps_rate: float = 10.0,
    commission_bps: float = 0.0,
    spread_stress_sensitivity: float = 5.0,
    adv_stress_sensitivity: float = 5.0,
) -> dict[str, float]:
    """
    Computes Endogenous Scenario-Dependent Liquidity-Adjusted Value-at-Risk (L-VaR)
    and Conditional Value-at-Risk (L-CVaR) across joint Monte Carlo return scenarios.

    Models:
    1. Endogenous spread widening under asset drawdowns:
       Spread_i(s) = Spread_{0, i} * (1 + kappa * max(0, -r_{i, s}))
    2. Endogenous market liquidity freeze (ADV contraction) under portfolio crashes:
       ADV_i(s) = ADV_{0, i} / (1 + eta * max(0, -r_{p, s}))
    3. Joint total stressed loss:
       L_stressed(s) = -r_{p, s} + c_liq(weights, s)

    Returns:
        dict containing market risk, deterministic baseline L-risk, and endogenous stressed L-risk.
    """
    if spread_stress_sensitivity < 0.0 or adv_stress_sensitivity < 0.0:
        raise ValueError("Stress sensitivities (kappa, eta) must be non-negative.")

    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be strictly between 0 and 1.")

    if portfolio_equity <= 0 or simulated_returns.size == 0 or len(tickers) == 0:
        return {
            "market_var": 0.0,
            "market_cvar": 0.0,
            "deterministic_l_var": 0.0,
            "deterministic_l_cvar": 0.0,
            "stressed_l_var": 0.0,
            "stressed_l_cvar": 0.0,
            "average_liquidation_cost_pct": 0.0,
            "average_liquidation_cost": 0.0,
        }

    if not np.all(np.isfinite(simulated_returns)):
        raise ValueError("simulated_returns must contain finite numerical values.")

    M, N = simulated_returns.shape
    horizon = max(0.1, float(execution_horizon_days))
    spread_map = spread_bps_dict or {}

    # Weight vector aligned with tickers
    w_arr = np.array([max(0.0, float(weights.get(tk, 0.0))) for tk in tickers], dtype=np.float64)
    w_sum = float(np.sum(w_arr))
    if w_sum > 1e-12:
        # Scale to ensure total weight does not exceed 1.0
        if w_sum > 1.0:
            w_arr = w_arr / w_sum

    notionals = w_arr * portfolio_equity  # shape (N,)

    # Baseline market parameters aligned with tickers
    base_spreads = np.array([max(0.0, float(spread_map.get(tk, 5.0))) for tk in tickers], dtype=np.float64)
    base_advs = np.array([max(1000.0, float(adv_dict.get(tk, 10_000_000.0))) for tk in tickers], dtype=np.float64)
    ann_vols = np.array([max(0.001, float(volatility_dict.get(tk, 0.20))) for tk in tickers], dtype=np.float64)
    daily_vols = ann_vols / math.sqrt(252.0)

    # 1. Portfolio scenario returns & market loss: shape (M,)
    # r_p = sum_i w_i * r_{i, s}
    port_rets = np.dot(simulated_returns, w_arr)  # shape (M,)
    market_loss = -port_rets                      # shape (M,)

    # 2. Endogenous Stress Shifts
    # Asset-level negative returns: max(0.0, -r_{i, s})
    neg_r_asset = np.maximum(0.0, -simulated_returns)  # shape (M, N)
    # Portfolio-level negative returns: max(0.0, -r_p)
    neg_r_port = np.maximum(0.0, market_loss)          # shape (M,)

    kappa = max(0.0, float(spread_stress_sensitivity))
    eta = max(0.0, float(adv_stress_sensitivity))

    # Stressed Spreads: shape (M, N)
    stressed_spreads = base_spreads[np.newaxis, :] * (1.0 + kappa * neg_r_asset)

    # Stressed ADVs: shape (M, N)
    # adv_divisor: shape (M, 1)
    adv_divisor = 1.0 + eta * neg_r_port[:, np.newaxis]
    stressed_advs = np.maximum(100.0, base_advs[np.newaxis, :] / adv_divisor)

    # 3. Vectorized Scenario Liquidation Costs
    # notional: shape (N,) broadcasted to (M, N)
    n_mat = notionals[np.newaxis, :]
    sig_mat = daily_vols[np.newaxis, :]

    # Participation rate per scenario & asset: shape (M, N)
    pr_mat = n_mat / (stressed_advs * horizon)

    if impact_model == "square_root":
        # Spread cost: notional * (spread_bps * 1e-4 / 2)
        c_spread = n_mat * (stressed_spreads * 1e-4 / 2.0)
        # Temp impact: notional * c_temp * daily_vol * sqrt(min(PR, 2.0))
        c_temp_cost = n_mat * (c_temp * sig_mat * np.sqrt(np.minimum(pr_mat, 2.0)))
        # Perm impact: notional * c_perm * daily_vol * min(notional / ADV, 1.0)
        c_perm_cost = n_mat * (c_perm * sig_mat * np.minimum(n_mat / stressed_advs, 1.0))
        # Commission: notional * (commission_bps * 1e-4)
        c_comm = n_mat * (commission_bps * 1e-4)
        scenario_costs_mat = c_spread + c_temp_cost + c_perm_cost + c_comm

    elif impact_model == "linear":
        c_spread = n_mat * (stressed_spreads * 1e-4 / 2.0)
        c_temp_cost = n_mat * (c_temp * sig_mat * pr_mat)
        c_perm_cost = n_mat * (c_perm * sig_mat * (n_mat / stressed_advs))
        c_comm = n_mat * (commission_bps * 1e-4)
        scenario_costs_mat = c_spread + c_temp_cost + c_perm_cost + c_comm

    else:
        # fixed_bps baseline with spread widening sensitivity
        c_spread = n_mat * (fixed_bps_rate * 1e-4 * (1.0 + kappa * neg_r_asset))
        scenario_costs_mat = c_spread

    # Total liquidation cost in dollars for each scenario: shape (M,)
    liq_cost_dollars = np.sum(scenario_costs_mat, axis=1)
    # Liquidation cost rate as fraction of portfolio equity: shape (M,)
    liq_cost_frac = liq_cost_dollars / portfolio_equity

    # 4. Total Stressed Loss Distribution: shape (M,)
    total_stressed_loss = market_loss + liq_cost_frac

    # 5. Risk Quantiles (Loss distribution: positive numbers are losses)
    alpha = float(confidence_level)
    market_var = float(np.quantile(market_loss, alpha))
    tail_mask_market = market_loss >= market_var
    market_cvar = float(np.mean(market_loss[tail_mask_market])) if np.any(tail_mask_market) else market_var

    stressed_var = float(np.quantile(total_stressed_loss, alpha))
    tail_mask_stressed = total_stressed_loss >= stressed_var
    stressed_cvar = float(np.mean(total_stressed_loss[tail_mask_stressed])) if np.any(tail_mask_stressed) else stressed_var

    # Deterministic baseline liquidation cost (scenario with 0 returns)
    base_det_cost = float(np.mean(liq_cost_frac[market_loss <= 0.0])) if np.any(market_loss <= 0.0) else float(np.mean(liq_cost_frac))

    return {
        "market_var": round(market_var, 4),
        "market_cvar": round(market_cvar, 4),
        "deterministic_l_var": round(market_var + base_det_cost, 4),
        "deterministic_l_cvar": round(market_cvar + base_det_cost, 4),
        "stressed_l_var": round(stressed_var, 4),
        "stressed_l_cvar": round(stressed_cvar, 4),
        "average_liquidation_cost_pct": round(float(np.mean(liq_cost_frac)), 4),
        "average_liquidation_cost": round(float(np.mean(liq_cost_dollars)), 2),
    }


def compute_daily_liquidation_loss(
    held_weights: np.ndarray,
    portfolio_equity: float,
    adv_arr: np.ndarray,
    vol_arr: np.ndarray,
    base_spreads_bps: np.ndarray,
    r_today: np.ndarray,
    portfolio_gross_ret: float,
    execution_horizon_days: float = 1.0,
    impact_model: Literal["square_root", "linear", "fixed_bps"] = "square_root",
    c_temp: float = 0.5,
    c_perm: float = 0.1,
    fixed_bps_rate: float = 10.0,
    commission_bps: float = 0.0,
    spread_stress_sensitivity: float = 0.0,
    adv_stress_sensitivity: float = 0.0,
    enable_endogenous_liquidity: bool = True,
) -> tuple[float, float, float, float]:
    """
    Computes daily deterministic and stressed liquidation costs as a fraction of portfolio equity,
    and returns (loss_det, loss_stressed, c_liq_det, c_liq_stressed).

    Formula (DEF-35-02):
        l_t^{det}      = -R_{p, t}^{gross} + c_{liq, t}^{det}
        l_t^{stressed} = -R_{p, t}^{gross} + c_{liq, t}^{stressed}
    """
    w_arr = np.maximum(0.0, np.asarray(held_weights, dtype=np.float64))
    if portfolio_equity <= 0 or w_arr.size == 0 or np.sum(w_arr) <= 1e-12:
        loss = -float(portfolio_gross_ret)
        return loss, loss, 0.0, 0.0

    r_arr = np.asarray(r_today, dtype=np.float64)
    kappa = max(0.0, float(spread_stress_sensitivity))
    eta = max(0.0, float(adv_stress_sensitivity))

    if impact_model == "fixed_bps":
        base_rate = float(fixed_bps_rate) * 1e-4
        c_liq_det = float(np.sum(w_arr) * base_rate)
        if enable_endogenous_liquidity and kappa > 0.0:
            neg_r = np.maximum(0.0, -r_arr)
            stressed_rates = base_rate * (1.0 + kappa * neg_r)
            c_liq_stressed = float(np.sum(w_arr * stressed_rates))
        else:
            c_liq_stressed = c_liq_det
    else:
        horizon = max(0.1, float(execution_horizon_days))
        notionals = w_arr * portfolio_equity
        daily_vols = np.asarray(vol_arr, dtype=np.float64) / math.sqrt(252.0)
        spreads = np.asarray(base_spreads_bps, dtype=np.float64)
        advs = np.maximum(1000.0, np.asarray(adv_arr, dtype=np.float64))

        # Deterministic
        pr_det = notionals / (advs * horizon)
        c_spread_det = notionals * (spreads * 1e-4 / 2.0)
        if impact_model == "square_root":
            c_temp_det = notionals * (c_temp * daily_vols * np.sqrt(np.minimum(pr_det, 2.0)))
            c_perm_det = notionals * (c_perm * daily_vols * np.minimum(notionals / advs, 1.0))
        else:  # linear
            c_temp_det = notionals * (c_temp * daily_vols * pr_det)
            c_perm_det = notionals * (c_perm * daily_vols * (notionals / advs))
        c_comm_det = notionals * (commission_bps * 1e-4)
        total_det_cost = float(np.sum(c_spread_det + c_temp_det + c_perm_det + c_comm_det))
        c_liq_det = total_det_cost / portfolio_equity if portfolio_equity > 0 else 0.0

        # Stressed
        if enable_endogenous_liquidity and (kappa > 0.0 or eta > 0.0):
            neg_r = np.maximum(0.0, -r_arr)
            neg_port = max(0.0, -float(portfolio_gross_ret))
            stressed_spreads = spreads * (1.0 + kappa * neg_r)
            stressed_advs = np.maximum(100.0, advs / (1.0 + eta * neg_port))
            pr_str = notionals / (stressed_advs * horizon)
            c_spread_str = notionals * (stressed_spreads * 1e-4 / 2.0)
            if impact_model == "square_root":
                c_temp_str = notionals * (c_temp * daily_vols * np.sqrt(np.minimum(pr_str, 2.0)))
                c_perm_str = notionals * (c_perm * daily_vols * np.minimum(notionals / stressed_advs, 1.0))
            else:
                c_temp_str = notionals * (c_temp * daily_vols * pr_str)
                c_perm_str = notionals * (c_perm * daily_vols * (notionals / stressed_advs))
            c_comm_str = notionals * (commission_bps * 1e-4)
            total_str_cost = float(np.sum(c_spread_str + c_temp_str + c_perm_str + c_comm_str))
            c_liq_stressed = total_str_cost / portfolio_equity if portfolio_equity > 0 else 0.0
        else:
            c_liq_stressed = c_liq_det

    loss_det = -float(portfolio_gross_ret) + c_liq_det
    loss_stressed = -float(portfolio_gross_ret) + c_liq_stressed
    return loss_det, loss_stressed, c_liq_det, c_liq_stressed


def compute_regime_aware_execution_parameters(
    base_participation_rate: float,
    base_risk_aversion: float,
    regime_probs: list[float] | np.ndarray | None,
    regime_adaptation_strength: float = 0.5,
    min_participation_rate: float = 0.02,
    max_participation_rate_upper: float | None = None,
) -> dict[str, Any]:
    """
    Computes adaptive, regime-aware execution parameters based on market regime belief probabilities.

    In a turbulent/crisis market regime (state with highest variance), market depth is fragile
    and liquidating large blocks creates disproportionate market impact. The policy:
    1. Contracts the effective participation rate:
       g_p = 1.0 - regime_adaptation_strength * p_turbulent
       p_eff = clip(base_participation_rate * g_p, min_participation_rate, max_participation_rate_upper)
    2. Scales the Almgren-Chriss risk-aversion parameter lambda:
       g_lambda = 1.0 + regime_adaptation_strength * p_turbulent
       lambda_eff = clip(base_risk_aversion * g_lambda, 0.0, 1.0)
       Note: If base_risk_aversion == 0.0, lambda_eff remains 0.0 identically, preserving TWAP convergence.

    Args:
        base_participation_rate: Unadjusted baseline daily participation rate (0 < PR <= 1.0).
        base_risk_aversion: Unadjusted baseline Almgren-Chriss risk aversion lambda (>= 0.0).
        regime_probs: List or array of M state belief probabilities, ordered from calm (state 0) to turbulent (state M-1).
        regime_adaptation_strength: Sensitivity factor in [0.0, 1.0]. 0.0 = no adaptation.
        min_participation_rate: Lower bound floor on participation rate.
        max_participation_rate_upper: Upper bound ceiling (defaults to base_participation_rate).

    Returns:
        dict containing:
            effective_participation_rate: float in [min_p, max_p]
            effective_risk_aversion: float >= 0.0
            regime_state: int (argmax of regime_probs)
            regime_probabilities: list[float]
            p_turbulent: float
            adaptation_factor_p: float
            adaptation_factor_lambda: float
    """
    if base_participation_rate <= 0.0 or base_participation_rate > 1.0:
        raise ValueError(f"base_participation_rate must be in (0, 1], got {base_participation_rate}")
    if base_risk_aversion < 0.0:
        raise ValueError(f"base_risk_aversion must be >= 0.0, got {base_risk_aversion}")
    if regime_adaptation_strength < 0.0 or regime_adaptation_strength > 1.0:
        raise ValueError(f"regime_adaptation_strength must be in [0, 1], got {regime_adaptation_strength}")
    if min_participation_rate <= 0.0:
        raise ValueError(f"min_participation_rate must be > 0.0, got {min_participation_rate}")
    if min_participation_rate > base_participation_rate:
        raise ValueError(f"min_participation_rate ({min_participation_rate}) cannot exceed base_participation_rate ({base_participation_rate})")

    p_upper = max_participation_rate_upper if max_participation_rate_upper is not None else base_participation_rate
    p_upper = max(min_participation_rate, min(1.0, float(p_upper)))

    if regime_probs is None or len(regime_probs) == 0:
        return {
            "effective_participation_rate": float(base_participation_rate),
            "effective_risk_aversion": float(base_risk_aversion),
            "regime_state": 0,
            "regime_probabilities": [1.0],
            "p_turbulent": 0.0,
            "adaptation_factor_p": 1.0,
            "adaptation_factor_lambda": 1.0,
            "fallback_used": True,
        }

    try:
        probs_arr = np.asarray(regime_probs, dtype=np.float64)
        if not np.all(np.isfinite(probs_arr)) or np.any(probs_arr < 0.0):
            return {
                "effective_participation_rate": float(base_participation_rate),
                "effective_risk_aversion": float(base_risk_aversion),
                "regime_state": 0,
                "regime_probabilities": [1.0 / len(probs_arr)] * len(probs_arr),
                "p_turbulent": 0.0,
                "adaptation_factor_p": 1.0,
                "adaptation_factor_lambda": 1.0,
                "fallback_used": True,
            }
    except Exception:
        return {
            "effective_participation_rate": float(base_participation_rate),
            "effective_risk_aversion": float(base_risk_aversion),
            "regime_state": 0,
            "regime_probabilities": [1.0],
            "p_turbulent": 0.0,
            "adaptation_factor_p": 1.0,
            "adaptation_factor_lambda": 1.0,
            "fallback_used": True,
        }

    probs_sum = float(np.sum(probs_arr))
    if probs_sum > 1e-12:
        probs_norm = probs_arr / probs_sum
    else:
        probs_norm = np.full(len(probs_arr), 1.0 / len(probs_arr))

    # In sorted HMM, state M - 1 represents the highest volatility / crisis / turbulent regime
    M = len(probs_norm)
    p_turbulent = float(probs_norm[M - 1])
    regime_state = int(np.argmax(probs_norm))

    # Adaptation multipliers
    g_p = max(0.0, 1.0 - (regime_adaptation_strength * p_turbulent))
    eff_p = float(np.clip(base_participation_rate * g_p, min_participation_rate, p_upper))

    g_lam = 1.0 + (regime_adaptation_strength * p_turbulent)
    eff_lam = float(np.clip(base_risk_aversion * g_lam, 0.0, 1.0)) if base_risk_aversion > 0 else 0.0

    return {
        "effective_participation_rate": eff_p,
        "effective_risk_aversion": eff_lam,
        "regime_state": regime_state,
        "regime_probabilities": [round(float(p), 4) for p in probs_norm],
        "p_turbulent": p_turbulent,
        "adaptation_factor_p": g_p,
        "adaptation_factor_lambda": g_lam,
        "fallback_used": False,
    }


def compute_execution_horizon(
    order_notionals: dict[str, float],
    adv_dict: dict[str, float],
    max_participation_rate: float = 0.10,
    max_scheduling_days: int = 5,
    default_adv: float = 10_000_000.0,
) -> dict[str, Any]:
    """
    Computes the required execution horizon in days based on order notionals and daily volume participation caps.

    Formula per asset i:
        D_i = min(D_max, max(1, ceil(|Delta N_i| / (ADV_i * PR_max))))
        D = max_i D_i

    Args:
        order_notionals: Dict mapping ticker to intended trade notional in currency (can be positive or negative).
        adv_dict: Dict mapping ticker to Average Daily Dollar Volume.
        max_participation_rate: Maximum fraction of ADV allowed to trade in a single day (0 < PR_max <= 1.0).
        max_scheduling_days: Upper bound on scheduling horizon D_max (>= 1).
        default_adv: Fallback ADV if missing or non-positive.

    Returns:
        dict containing:
            horizon_days: Overall execution horizon D (int >= 1)
            per_asset_days: Dict mapping ticker to D_i
            participation_exceeded: True if any order required D_i > 1
    """
    if max_participation_rate <= 0.0 or max_participation_rate > 1.0:
        raise ValueError(f"max_participation_rate must be in (0, 1], got {max_participation_rate}")
    if max_scheduling_days < 1:
        raise ValueError(f"max_scheduling_days must be >= 1, got {max_scheduling_days}")

    per_asset_days: dict[str, int] = {}
    exceeded = False

    for tk, notional in order_notionals.items():
        trade_val = abs(float(notional))
        if trade_val <= 1e-6:
            per_asset_days[tk] = 1
            continue

        raw_adv = adv_dict.get(tk, default_adv)
        adv = float(raw_adv) if (raw_adv is not None and float(raw_adv) > 0.0) else default_adv
        daily_cap = adv * max_participation_rate

        if daily_cap <= 1e-12:
            req_days = max_scheduling_days
        else:
            req_days = int(math.ceil(trade_val / daily_cap))

        d_i = min(int(max_scheduling_days), max(1, req_days))
        per_asset_days[tk] = d_i
        if d_i > 1 or req_days > 1:
            exceeded = True

    overall_d = max(per_asset_days.values()) if per_asset_days else 1
    return {
        "horizon_days": overall_d,
        "per_asset_days": per_asset_days,
        "participation_exceeded": exceeded,
    }


def compute_multi_day_execution_schedule(
    order_notionals: dict[str, float],
    adv_dict: dict[str, float],
    volatility_dict: dict[str, float] | None = None,
    max_participation_rate: float = 0.10,
    max_scheduling_days: int = 5,
    scheduling_mode: str = "twap",
    scheduling_risk_aversion: float = 1e-6,
    volume_profile: list[float] | None = None,
    default_adv: float = 10_000_000.0,
    c_temp: float = 0.5,
    regime_probs: list[float] | np.ndarray | None = None,
    regime_adaptation_strength: float = 0.0,
    min_participation_rate: float = 0.02,
) -> dict[str, Any]:
    """
    Computes daily execution tranches across multiple trading days using TWAP, VWAP, or Almgren-Chriss trajectories,
    with optional market regime adaptation.

    Args:
        order_notionals: Dict mapping ticker to signed trade notional: (w_target - w_pre) * Equity.
        adv_dict: Dict mapping ticker to Average Daily Dollar Volume.
        volatility_dict: Dict mapping ticker to annualized volatility (required for Almgren-Chriss).
        max_participation_rate: Maximum fraction of ADV allowed per day.
        max_scheduling_days: Maximum allowable scheduling window.
        scheduling_mode: 'single_day', 'twap', 'vwap', or 'almgren_chriss'.
        scheduling_risk_aversion: Risk aversion lambda for Almgren-Chriss (>= 0).
        volume_profile: Optional list of D volume fractions for VWAP. If None, falls back to uniform (TWAP).
        default_adv: Fallback ADV.
        c_temp: Temporary market impact factor.
        regime_probs: Optional list of M regime belief probabilities.
        regime_adaptation_strength: Factor in [0, 1] controlling regime-adaptive participation and risk aversion.
        min_participation_rate: Floor on participation rate under regime contraction.

    Returns:
        dict containing:
            horizon_days: D (int >= 1)
            scheduling_mode: str
            daily_schedules: list of D dicts, each mapping ticker to that day's signed trade tranche.
            total_scheduled_notionals: dict mapping ticker to sum of tranches.
            per_asset_diagnostics: dict mapping ticker to diagnostic metrics.
            regime_diagnostics: dict of regime-adapted parameters if enabled.
    """
    valid_modes = {"single_day", "twap", "vwap", "almgren_chriss"}
    if scheduling_mode not in valid_modes:
        raise ValueError(f"Invalid scheduling_mode '{scheduling_mode}', must be one of {valid_modes}")

    # Compute regime-aware parameters if regime adaptation is active
    effective_pr = max_participation_rate
    effective_lambda = scheduling_risk_aversion
    regime_diag = None

    if regime_probs is not None and regime_adaptation_strength > 0.0:
        regime_diag = compute_regime_aware_execution_parameters(
            base_participation_rate=max_participation_rate,
            base_risk_aversion=scheduling_risk_aversion,
            regime_probs=regime_probs,
            regime_adaptation_strength=regime_adaptation_strength,
            min_participation_rate=min_participation_rate,
            max_participation_rate_upper=max_participation_rate,
        )
        effective_pr = regime_diag["effective_participation_rate"]
        effective_lambda = regime_diag["effective_risk_aversion"]

    horizon_info = compute_execution_horizon(
        order_notionals=order_notionals,
        adv_dict=adv_dict,
        max_participation_rate=effective_pr,
        max_scheduling_days=max_scheduling_days,
        default_adv=default_adv,
    )
    D = int(horizon_info["horizon_days"])
    if scheduling_mode == "single_day":
        D = 1

    vols = volatility_dict or {}
    daily_schedules: list[dict[str, float]] = [{} for _ in range(D)]
    total_scheduled: dict[str, float] = {}
    diagnostics: dict[str, Any] = {}

    for tk, raw_notional in order_notionals.items():
        notional = float(raw_notional)
        if abs(notional) <= 1e-6 or D == 1:
            for d in range(D):
                daily_schedules[d][tk] = notional if d == 0 else 0.0
            total_scheduled[tk] = notional
            diagnostics[tk] = {
                "horizon_days": D,
                "scheduling_mode": scheduling_mode,
                "direction": "buy" if notional > 0 else ("sell" if notional < 0 else "neutral"),
                "total_notional": notional,
            }
            continue

        direction = 1.0 if notional > 0 else -1.0
        mag = abs(notional)

        if scheduling_mode == "twap":
            # Uniform slicing across D days
            daily_mag = mag / D
            for d in range(D):
                daily_schedules[d][tk] = direction * daily_mag

        elif scheduling_mode == "vwap":
            # Volume-weighted profile
            if volume_profile is not None and len(volume_profile) == D and sum(volume_profile) > 1e-12:
                vp_sum = float(sum(volume_profile))
                weights = [float(v) / vp_sum for v in volume_profile]
            else:
                weights = [1.0 / D] * D
            for d in range(D):
                daily_schedules[d][tk] = direction * (mag * weights[d])

        elif scheduling_mode == "almgren_chriss":
            # Almgren-Chriss Optimal Trajectory
            raw_vol = float(vols.get(tk, 0.20))
            ann_vol = max(0.001, raw_vol)
            daily_vol = ann_vol / math.sqrt(252.0)
            raw_adv = adv_dict.get(tk, default_adv)
            adv = float(raw_adv) if (raw_adv is not None and float(raw_adv) > 0.0) else default_adv
            lam = max(0.0, float(effective_lambda))

            # Temporary impact factor
            eta = max(1e-12, float((daily_vol / (0.10 * adv)) * c_temp))
            tau = 1.0  # Daily periods
            arg = 1.0 + 0.5 * (lam * (daily_vol**2) * (tau**2)) / eta
            kappa = math.acosh(max(1.0, arg)) / tau

            if kappa < 1e-6:
                # Risk-neutral limit -> linear TWAP
                daily_mag = mag / D
                for d in range(D):
                    daily_schedules[d][tk] = direction * daily_mag
            else:
                sinh_kD = math.sinh(kappa * D)
                x_rem = np.zeros(D + 1, dtype=np.float64)
                x_rem[0] = mag
                for d_idx in range(1, D):
                    t_rem = D - d_idx
                    x_rem[d_idx] = mag * (math.sinh(kappa * t_rem) / sinh_kD)
                x_rem[D] = 0.0

                tranches = np.maximum(0.0, np.diff(-x_rem))
                if np.sum(tranches) > 0:
                    tranches = tranches * (mag / np.sum(tranches))
                for d in range(D):
                    daily_schedules[d][tk] = direction * float(tranches[d])

        total_scheduled[tk] = sum(daily_schedules[d][tk] for d in range(D))
        diagnostics[tk] = {
            "horizon_days": D,
            "scheduling_mode": scheduling_mode,
            "direction": "buy" if notional > 0 else "sell",
            "total_notional": notional,
            "sum_scheduled": total_scheduled[tk],
        }

    return {
        "horizon_days": D,
        "scheduling_mode": scheduling_mode,
        "daily_schedules": daily_schedules,
        "total_scheduled_notionals": total_scheduled,
        "per_asset_diagnostics": diagnostics,
        "effective_participation_rate": effective_pr,
        "effective_risk_aversion": effective_lambda,
        "regime_diagnostics": regime_diag,
    }


