"""
Service orchestration for Black-Litterman portfolio optimization,
Bayesian view incorporation, and chronological out-of-sample backtesting.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, status
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.backtesting.data import prepare_backtest_data
from app.backtesting.engine import run_portfolio_simulation
from app.db.models import UserModel
from app.quant.black_litterman import (
    BlackLittermanView,
    calculate_implied_equilibrium_returns,
    build_view_matrices,
    compute_black_litterman_posterior,
    compute_unconstrained_bl_weights,
    optimize_black_litterman_portfolio,
    compute_black_litterman_diagnostics,
)
from app.quant.covariance import covariance_matrix
from app.quant.returns import simple_returns
from app.black_litterman.models import (
    BlackLittermanBacktestRequest,
    BlackLittermanBacktestResponse,
    BlackLittermanOptimizeRequest,
    BlackLittermanOptimizeResponse,
    ViewSummaryItem,
)


def _build_asset_resolver(resolved_assets: list[str]) -> dict[str, str]:
    resolver: dict[str, str] = {}
    for canonical in resolved_assets:
        resolver[canonical] = canonical
        resolver[canonical.upper()] = canonical
        if ":" in canonical:
            ticker = canonical.split(":")[0]
            resolver[ticker] = canonical
            resolver[ticker.upper()] = canonical
    return resolver


def execute_black_litterman_optimization(
    request: BlackLittermanOptimizeRequest,
    current_user: UserModel,
    session: Session,
) -> BlackLittermanOptimizeResponse:
    """
    Executes Black-Litterman Bayesian portfolio optimization:
    1. Derives prior equilibrium implied returns.
    2. Builds view matrices P, q, Omega with confidence scaling.
    3. Derives posterior distribution mu_BL, Sigma_post.
    4. Computes unconstrained and constrained allocations.
    5. Computes active tilt and view diagnostics.
    """
    start_d = date.fromisoformat(request.start_date) if request.start_date else None
    end_d = date.fromisoformat(request.end_date) if request.end_date else None

    # Fetch and validate historical price matrix
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=start_d,
        end_date=end_d,
        user=current_user,
        session=session,
        min_required_observations=len(request.assets) + 2,
    )

    n = len(resolved_assets)
    resolver = _build_asset_resolver(resolved_assets)

    # Compute daily simple returns and annualized covariance
    ret_df = simple_returns(clean_prices)
    cov_df = covariance_matrix(
        ret_df,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )
    cov = cov_df.values.astype(np.float64)

    # Determine equilibrium weights w_eq
    if request.equilibrium_weights:
        raw_eq = np.array([
            request.equilibrium_weights.get(a, request.equilibrium_weights.get(a.split(":")[0], 0.0))
            for a in resolved_assets
        ], dtype=np.float64)
        sum_eq = np.sum(raw_eq)
        if sum_eq <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Equilibrium weights must sum to a positive value.",
            )
        w_eq = raw_eq / sum_eq
    else:
        # Default: equal weight
        w_eq = np.full(n, 1.0 / n, dtype=np.float64)

    # Step 1: Equilibrium implied returns Pi
    pi = calculate_implied_equilibrium_returns(
        covariance=cov,
        equilibrium_weights=w_eq,
        risk_aversion=request.risk_aversion,
        risk_free_rate=request.risk_free_rate,
    )

    # Step 2: Formulate views P, q, Omega
    view_objs = [
        BlackLittermanView(
            view_type=v.view_type,
            assets=tuple(resolver.get(a, resolver.get(a.upper(), a)) for a in v.assets),
            weights=tuple(v.weights),
            target_return=v.target_return,
            confidence=v.confidence,
        )
        for v in request.views
    ]

    try:
        p, q, omega = build_view_matrices(
            views=view_objs,
            asset_order=resolved_assets,
            tau=request.tau,
            covariance=cov,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Step 3: Compute posterior distribution
    mu_bl, sigma_post = compute_black_litterman_posterior(
        implied_returns=pi,
        covariance=cov,
        p=p,
        q=q,
        omega=omega,
        tau=request.tau,
    )

    # Step 4: Unconstrained and Constrained weights
    w_unconstrained = compute_unconstrained_bl_weights(
        posterior_mean=mu_bl,
        covariance=cov,
        risk_aversion=request.risk_aversion,
        risk_free_rate=request.risk_free_rate,
    )

    opt_res = optimize_black_litterman_portfolio(
        posterior_mean=mu_bl,
        posterior_covariance=sigma_post,
        objective=request.objective,
        risk_free_rate=request.risk_free_rate,
        risk_aversion=request.risk_aversion,
        min_weight=request.constraints.default_min_weight,
        max_weight=request.constraints.default_max_weight,
        max_gross_exposure=request.constraints.max_gross_exposure,
    )

    w_opt = opt_res["weights"]

    # Step 5: Diagnostics
    diagnostics = compute_black_litterman_diagnostics(
        asset_order=resolved_assets,
        equilibrium_weights=w_eq,
        optimal_weights=w_opt,
        implied_returns=pi,
        posterior_returns=mu_bl,
        views=view_objs,
        p=p,
        q=q,
    )

    view_summaries = [
        ViewSummaryItem(
            description=v["description"],
            view_type=v["view_type"],
            confidence=v["confidence"],
            target_return=v["target_return"],
            prior_expected_spread=v["prior_expected_spread"],
            posterior_expected_spread=v["posterior_expected_spread"],
            absorbed_difference=v["absorbed_difference"],
        )
        for v in diagnostics["views_summary"]
    ]

    return BlackLittermanOptimizeResponse(
        dataset_id=request.dataset_id,
        assets=resolved_assets,
        equilibrium_returns={resolved_assets[i]: float(pi[i]) for i in range(n)},
        posterior_returns={resolved_assets[i]: float(mu_bl[i]) for i in range(n)},
        prior_weights={resolved_assets[i]: float(w_eq[i]) for i in range(n)},
        unconstrained_bl_weights={resolved_assets[i]: float(w_unconstrained[i]) for i in range(n)},
        optimal_weights={resolved_assets[i]: float(w_opt[i]) for i in range(n)},
        active_tilts=diagnostics["active_tilts"],
        portfolio_metrics={
            "expected_return": opt_res["expected_return"],
            "volatility": opt_res["volatility"],
            "sharpe_ratio": opt_res["sharpe_ratio"],
        },
        diagnostics={
            "weight_distance_d1": diagnostics["weight_distance_d1"],
            "max_tilt_asset": diagnostics["max_tilt_asset"],
            "max_tilt_value": diagnostics["max_tilt_value"],
            "hhi_prior": diagnostics["hhi_prior"],
            "hhi_optimal": diagnostics["hhi_optimal"],
            "effective_assets_prior": diagnostics["effective_assets_prior"],
            "effective_assets_optimal": diagnostics["effective_assets_optimal"],
        },
        views_summary=view_summaries,
        is_feasible=opt_res["is_feasible"],
        solver_status=opt_res["solver_status"],
        solver_message=opt_res["solver_message"],
        warnings=warnings,
    )


def execute_black_litterman_backtest(
    request: BlackLittermanBacktestRequest,
    current_user: UserModel,
    session: Session,
) -> BlackLittermanBacktestResponse:
    """
    Executes chronological out-of-sample backtest of Black-Litterman strategy:
    1. Splits price history into strictly in-sample training and out-of-sample evaluation.
    2. Calculates implied returns and posterior parameters using training window only.
    3. Solves Black-Litterman allocations.
    4. Evaluates realized performance out-of-sample using deterministic simulation with transaction costs.
    """
    try:
        train_end_d = date.fromisoformat(request.train_end_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="train_end_date must be in YYYY-MM-DD format.",
        )

    # Load full historical price matrix
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=None,
        end_date=None,
        user=current_user,
        session=session,
        min_required_observations=len(request.assets) + 10,
    )

    n = len(resolved_assets)

    # Split into train (in-sample) and test (out-of-sample)
    split_date = request.train_end_date
    df_train = clean_prices[clean_prices.index <= split_date]
    df_test = clean_prices[clean_prices.index >= split_date]

    if len(df_train) < n + 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"In-sample training period has only {len(df_train)} bars. Minimum required is {n + 2}.",
        )
    if len(df_test) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Out-of-sample evaluation period has only {len(df_test)} bars. Minimum required is 5.",
        )

    # In-Sample Estimation: discrete simple returns and covariance
    train_ret = simple_returns(df_train)
    cov_train_df = covariance_matrix(
        train_ret,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )
    cov_train = cov_train_df.values.astype(np.float64)

    resolver = _build_asset_resolver(resolved_assets)

    # Equilibrium weights
    if request.equilibrium_weights:
        raw_eq = np.array([
            request.equilibrium_weights.get(a, request.equilibrium_weights.get(a.split(":")[0], 0.0))
            for a in resolved_assets
        ], dtype=np.float64)
        sum_eq = np.sum(raw_eq)
        w_eq = raw_eq / sum_eq if sum_eq > 0 else np.full(n, 1.0 / n, dtype=np.float64)
    else:
        w_eq = np.full(n, 1.0 / n, dtype=np.float64)

    # In-Sample Implied Returns
    pi = calculate_implied_equilibrium_returns(
        covariance=cov_train,
        equilibrium_weights=w_eq,
        risk_aversion=request.risk_aversion,
        risk_free_rate=request.risk_free_rate,
    )

    # Views matrix construction
    view_objs = [
        BlackLittermanView(
            view_type=v.view_type,
            assets=tuple(resolver.get(a, resolver.get(a.upper(), a)) for a in v.assets),
            weights=tuple(v.weights),
            target_return=v.target_return,
            confidence=v.confidence,
        )
        for v in request.views
    ]

    p, q, omega = build_view_matrices(
        views=view_objs,
        asset_order=resolved_assets,
        tau=request.tau,
        covariance=cov_train,
    )

    # In-Sample Posterior
    mu_bl, sigma_post = compute_black_litterman_posterior(
        implied_returns=pi,
        covariance=cov_train,
        p=p,
        q=q,
        omega=omega,
        tau=request.tau,
    )

    # Solve optimal weights strictly using in-sample posterior
    opt_res = optimize_black_litterman_portfolio(
        posterior_mean=mu_bl,
        posterior_covariance=sigma_post,
        objective=request.objective,
        risk_free_rate=request.risk_free_rate,
        risk_aversion=request.risk_aversion,
        min_weight=request.min_weight,
        max_weight=request.max_weight,
    )

    w_bl_opt = opt_res["weights"]

    # Map weights to dictionaries
    w_eq_map = {resolved_assets[i]: float(w_eq[i]) for i in range(n)}
    w_bl_map = {resolved_assets[i]: float(w_bl_opt[i]) for i in range(n)}
    active_tilts = {resolved_assets[i]: float(w_bl_opt[i] - w_eq[i]) for i in range(n)}

    # Simulate Out-of-Sample Performance on df_test
    initial_capital = 100000.0
    eq_metrics, eq_equity, _ = run_portfolio_simulation(
        prices=df_test,
        strategy_type="target_weights",
        target_weights=w_eq_map,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=initial_capital,
        transaction_cost_bps=request.cost_bps,
        slippage_bps=request.slippage_bps,
        periods_per_year=periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    bl_metrics, bl_equity, _ = run_portfolio_simulation(
        prices=df_test,
        strategy_type="target_weights",
        target_weights=w_bl_map,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=initial_capital,
        transaction_cost_bps=request.cost_bps,
        slippage_bps=request.slippage_bps,
        periods_per_year=periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    # Merge downsampled equity curves
    merged_curves = []
    num_pts = min(len(eq_equity), len(bl_equity))
    step = max(1, num_pts // 80)
    for i in range(0, num_pts, step):
        pt_e = eq_equity[i]
        pt_b = bl_equity[i]
        merged_curves.append({
            "date": pt_e.date,
            "equilibrium_portfolio_value": pt_e.portfolio_value_net,
            "black_litterman_portfolio_value": pt_b.portfolio_value_net,
            "equilibrium_drawdown": pt_e.drawdown_net,
            "black_litterman_drawdown": pt_b.drawdown_net,
        })

    # Include final point
    if merged_curves[-1]["date"] != eq_equity[-1].date:
        pt_e = eq_equity[-1]
        pt_b = bl_equity[-1]
        merged_curves.append({
            "date": pt_e.date,
            "equilibrium_portfolio_value": pt_e.portfolio_value_net,
            "black_litterman_portfolio_value": pt_b.portfolio_value_net,
            "equilibrium_drawdown": pt_e.drawdown_net,
            "black_litterman_drawdown": pt_b.drawdown_net,
        })

    return BlackLittermanBacktestResponse(
        dataset_id=request.dataset_id,
        assets=resolved_assets,
        train_period={"start": str(df_train.index[0]), "end": str(df_train.index[-1])},
        test_period={"start": str(df_test.index[0]), "end": str(df_test.index[-1])},
        equilibrium_weights=w_eq_map,
        optimal_weights=w_bl_map,
        active_tilts=active_tilts,
        equilibrium_kpis={
            "cumulative_return": eq_metrics.cumulative_return_net,
            "annualized_return": eq_metrics.annualized_return_net,
            "annualized_volatility": eq_metrics.volatility_annualized_net,
            "sharpe_ratio": eq_metrics.sharpe_ratio_net,
            "max_drawdown": eq_metrics.max_drawdown_net,
            "total_turnover": eq_metrics.total_turnover,
            "total_friction_costs": eq_metrics.total_friction_costs,
            "final_value": eq_metrics.final_value_net,
        },
        black_litterman_kpis={
            "cumulative_return": bl_metrics.cumulative_return_net,
            "annualized_return": bl_metrics.annualized_return_net,
            "annualized_volatility": bl_metrics.volatility_annualized_net,
            "sharpe_ratio": bl_metrics.sharpe_ratio_net,
            "max_drawdown": bl_metrics.max_drawdown_net,
            "total_turnover": bl_metrics.total_turnover,
            "total_friction_costs": bl_metrics.total_friction_costs,
            "final_value": bl_metrics.final_value_net,
        },
        equity_curves=merged_curves,
        warnings=warnings,
    )
