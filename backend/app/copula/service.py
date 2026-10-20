"""
Service Layer for Copula-Based Tail Dependency, Multivariate Return Simulation,
and Tail Risk Parity (TRP) Allocation.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.backtesting.data import prepare_backtest_data
from app.db.models import UserModel
from app.portfolio.service import get_dataset_assets
from app.quant.returns import simple_returns
from app.quant.copula_tail_risk import (
    compute_pseudo_observations,
    fit_pairwise_copulas,
    simulate_copula_returns,
    optimize_tail_risk_parity,
)
from app.quant.vine_copula import (
    fit_c_vine,
    fit_d_vine,
    simulate_vine_returns,
)
from app.copula.models import (
    CopulaFitRequest,
    CopulaFitResponse,
    CopulaSimulateRequest,
    CopulaSimulateResponse,
    TailRiskParityRequest,
    TailRiskParityResponse,
    VineCopulaFitRequest,
    VineCopulaFitResponse,
    VineCopulaSimulateRequest,
    VineCopulaSimulateResponse,
    VineTailRiskParityRequest,
    VineTailRiskParityResponse,
    VineBacktestRequest,
    VineBacktestResponse,
    VineEdge,
)
from app.quant.vine_backtest import run_vine_tail_risk_parity_backtest


def _load_copula_returns(
    dataset_id: str,
    requested_tickers: list[str] | None,
    current_user: UserModel,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    min_observations: int = 15,
) -> tuple[np.ndarray, list[str]]:
    """Loads clean price data and computes simple return matrix."""
    check_dataset_access(db, dataset_id, current_user)

    meta_assets = get_dataset_assets(dataset_id)
    if not meta_assets or len(meta_assets) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Copula tail risk analysis requires a dataset with at least 2 verified assets.",
        )

    ticker_to_asset_id = {a.ticker: a.asset_id for a in meta_assets}
    ticker_to_asset_id.update({a.asset_id: a.asset_id for a in meta_assets})

    resolved_asset_ids = []
    if requested_tickers:
        for t in requested_tickers:
            if t in ticker_to_asset_id:
                resolved_asset_ids.append(ticker_to_asset_id[t])
            else:
                resolved_asset_ids.append(t)
    else:
        resolved_asset_ids = [a.asset_id for a in meta_assets]

    if len(resolved_asset_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 distinct assets are required for multivariate copula dependence analysis.",
        )

    clean_prices, final_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=dataset_id,
        requested_assets=resolved_asset_ids,
        start_date=start_date,
        end_date=end_date,
        user=current_user,
        session=db,
        min_required_observations=min_observations,
    )

    if clean_prices.empty or len(clean_prices) < min_observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Copula estimation requires at least {min_observations} aligned price observations.",
        )

    # Compute daily simple returns (drop initial NaN from discrete differencing)
    ret_df = simple_returns(clean_prices).dropna()
    ret_matrix = ret_df.to_numpy(dtype=np.float64)

    # Bare ticker display names
    asset_id_to_ticker = {a.asset_id: a.ticker for a in meta_assets}
    display_tickers = [asset_id_to_ticker.get(a_id, a_id) for a_id in final_assets]

    return ret_matrix, display_tickers


def execute_copula_fit(
    request: CopulaFitRequest,
    current_user: UserModel,
    db: Session,
) -> CopulaFitResponse:
    """Estimates copula dependence parameters and tail dependence matrices."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        U, _ = compute_pseudo_observations(ret_matrix, method=request.marginal_method)
        fit_results = fit_pairwise_copulas(
            U=U,
            tickers=tickers,
            copula_type=request.copula_type,
        )

        return CopulaFitResponse(
            dataset_id=request.dataset_id,
            copula_type=request.copula_type,
            marginal_method=request.marginal_method,
            tickers=tickers,
            tail_dependence_matrix=fit_results["tail_dependence_matrix"],
            kendall_tau_matrix=fit_results["kendall_tau_matrix"],
            pearson_corr_matrix=fit_results["pearson_corr_matrix"],
            pairwise_results=fit_results["pairwise_results"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Copula parameter estimation failed: {str(exc)}",
        ) from exc


def execute_copula_simulation(
    request: CopulaSimulateRequest,
    current_user: UserModel,
    db: Session,
) -> CopulaSimulateResponse:
    """Simulates multivariate return scenarios preserving copula tail dependence."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        sim_returns, diagnostics = simulate_copula_returns(
            returns=ret_matrix,
            tickers=tickers,
            copula_type=request.copula_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            marginal_method=request.marginal_method,
        )

        means = {tickers[i]: round(float(np.mean(sim_returns[:, i]) * 252.0), 4) for i in range(len(tickers))}
        vols = {tickers[i]: round(float(np.std(sim_returns[:, i]) * np.sqrt(252.0)), 4) for i in range(len(tickers))}
        corr_matrix = np.corrcoef(sim_returns, rowvar=False).round(4).tolist()

        # Format first 50 sample scenarios for visualization
        sample_scenarios = [
            {tickers[j]: round(float(sim_returns[i, j]), 5) for j in range(len(tickers))}
            for i in range(min(50, sim_returns.shape[0]))
        ]

        return CopulaSimulateResponse(
            dataset_id=request.dataset_id,
            copula_type=request.copula_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            tickers=tickers,
            simulated_means=means,
            simulated_volatilities=vols,
            sample_correlation_matrix=corr_matrix,
            sample_scenarios=sample_scenarios,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Copula simulation failed: {str(exc)}",
        ) from exc


def execute_tail_risk_parity(
    request: TailRiskParityRequest,
    current_user: UserModel,
    db: Session,
) -> TailRiskParityResponse:
    """Solves for Tail Risk Parity (TRP) allocation under simulated copula scenarios."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        sim_returns, _ = simulate_copula_returns(
            returns=ret_matrix,
            tickers=tickers,
            copula_type=request.copula_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            marginal_method=request.marginal_method,
        )

        opt_result = optimize_tail_risk_parity(
            simulated_returns=sim_returns,
            tickers=tickers,
            confidence_level=request.confidence_level,
            max_iter=500,
        )

        return TailRiskParityResponse(
            dataset_id=request.dataset_id,
            copula_type=request.copula_type,
            confidence_level=request.confidence_level,
            converged=opt_result["converged"],
            weights=opt_result["weights"],
            tail_risk_contributions=opt_result["tail_risk_contributions"],
            portfolio_var=opt_result["portfolio_var"],
            portfolio_cvar=opt_result["portfolio_cvar"],
            euler_reconciliation_error=opt_result["euler_reconciliation_error"],
            simulated_loss_distribution=opt_result["simulated_loss_distribution"],
            baselines=opt_result["baselines"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tail Risk Parity optimization failed: {str(exc)}",
        ) from exc


# ============================================================================
# Regular Vine Copula (Stage 23) Service Functions
# ============================================================================

def execute_vine_copula_fit(
    request: VineCopulaFitRequest,
    current_user: UserModel,
    db: Session,
) -> VineCopulaFitResponse:
    """Estimates pair-copula parameters across trees in C-Vine or D-Vine structure."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        U, _ = compute_pseudo_observations(ret_matrix, method=request.marginal_method)
        if request.vine_type == "c_vine":
            fitted_vine = fit_c_vine(U, tickers, families=request.family_set)
        else:
            fitted_vine = fit_d_vine(U, tickers, families=request.family_set)

        formatted_trees: list[list[VineEdge]] = []
        for tree_edges in fitted_vine["trees"]:
            tree_list = [VineEdge(**edge) for edge in tree_edges]
            formatted_trees.append(tree_list)

        return VineCopulaFitResponse(
            dataset_id=request.dataset_id,
            vine_type=request.vine_type,
            marginal_method=request.marginal_method,
            ordered_tickers=fitted_vine["ordered_tickers"],
            dimension=fitted_vine["dimension"],
            trees=formatted_trees,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Vine Copula fitting failed: {str(exc)}",
        ) from exc


def execute_vine_copula_simulation(
    request: VineCopulaSimulateRequest,
    current_user: UserModel,
    db: Session,
) -> VineCopulaSimulateResponse:
    """Simulates multivariate return scenarios preserving vine copula conditional tree dependence."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        sim_returns, _ = simulate_vine_returns(
            returns=ret_matrix,
            tickers=tickers,
            vine_type=request.vine_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            marginal_method=request.marginal_method,
        )

        means = {tickers[i]: round(float(np.mean(sim_returns[:, i]) * 252.0), 4) for i in range(len(tickers))}
        vols = {tickers[i]: round(float(np.std(sim_returns[:, i]) * np.sqrt(252.0)), 4) for i in range(len(tickers))}
        corr_matrix = np.corrcoef(sim_returns, rowvar=False).round(4).tolist()

        sample_scenarios = [
            {tickers[j]: round(float(sim_returns[i, j]), 5) for j in range(len(tickers))}
            for i in range(min(50, sim_returns.shape[0]))
        ]

        return VineCopulaSimulateResponse(
            dataset_id=request.dataset_id,
            vine_type=request.vine_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            tickers=tickers,
            simulated_means=means,
            simulated_volatilities=vols,
            sample_correlation_matrix=corr_matrix,
            sample_scenarios=sample_scenarios,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Vine Copula simulation failed: {str(exc)}",
        ) from exc


def execute_vine_tail_risk_parity(
    request: VineTailRiskParityRequest,
    current_user: UserModel,
    db: Session,
) -> VineTailRiskParityResponse:
    """Solves for Tail Risk Parity (TRP) allocation under simulated vine copula scenarios."""
    ret_matrix, tickers = _load_copula_returns(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=15,
    )

    try:
        sim_returns, _ = simulate_vine_returns(
            returns=ret_matrix,
            tickers=tickers,
            vine_type=request.vine_type,
            num_simulations=request.num_simulations,
            random_seed=request.random_seed,
            marginal_method=request.marginal_method,
        )

        opt_result = optimize_tail_risk_parity(
            simulated_returns=sim_returns,
            tickers=tickers,
            confidence_level=request.confidence_level,
            max_iter=500,
        )

        return VineTailRiskParityResponse(
            dataset_id=request.dataset_id,
            vine_type=request.vine_type,
            confidence_level=request.confidence_level,
            converged=opt_result["converged"],
            weights=opt_result["weights"],
            tail_risk_contributions=opt_result["tail_risk_contributions"],
            portfolio_var=opt_result["portfolio_var"],
            portfolio_cvar=opt_result["portfolio_cvar"],
            euler_reconciliation_error=opt_result["euler_reconciliation_error"],
            simulated_loss_distribution=opt_result["simulated_loss_distribution"],
            baselines=opt_result["baselines"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Vine Tail Risk Parity optimization failed: {str(exc)}",
        ) from exc


def _load_copula_returns_df(
    dataset_id: str,
    requested_tickers: list[str] | None,
    current_user: UserModel,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    min_observations: int = 35,
) -> tuple[pd.DataFrame, list[str]]:
    """Loads clean price data and computes simple return DataFrame with date index."""
    check_dataset_access(db, dataset_id, current_user)

    meta_assets = get_dataset_assets(dataset_id)
    if not meta_assets or len(meta_assets) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vine backtesting requires a dataset with at least 2 verified assets.",
        )

    ticker_to_asset_id = {a.ticker: a.asset_id for a in meta_assets}
    ticker_to_asset_id.update({a.asset_id: a.asset_id for a in meta_assets})

    resolved_asset_ids = []
    if requested_tickers:
        for t in requested_tickers:
            if t in ticker_to_asset_id:
                resolved_asset_ids.append(ticker_to_asset_id[t])
            else:
                resolved_asset_ids.append(t)
    else:
        resolved_asset_ids = [a.asset_id for a in meta_assets]

    if len(resolved_asset_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 distinct assets are required for Vine backtesting.",
        )

    clean_prices, final_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=dataset_id,
        requested_assets=resolved_asset_ids,
        start_date=start_date,
        end_date=end_date,
        user=current_user,
        session=db,
        min_required_observations=min_observations,
    )

    if clean_prices.empty or len(clean_prices) < min_observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Vine backtesting requires at least {min_observations} aligned price observations.",
        )

    ret_df = simple_returns(clean_prices).dropna()

    asset_id_to_ticker = {a.asset_id: a.ticker for a in meta_assets}
    display_tickers = [asset_id_to_ticker.get(a_id, a_id) for a_id in final_assets]
    ret_df.columns = display_tickers

    # Extract historical volumes if available in dataset rows
    volumes_df: pd.DataFrame | None = None
    try:
        raw_rows = get_dataset_rows(dataset_id)
        if raw_rows:
            vols_by_date_asset: dict[tuple[str, str], float] = {}
            for r in raw_rows:
                row_aid = f"{r.get('ticker')}:{r.get('market')}"
                if row_aid not in final_assets:
                    continue
                d_str = r.get("date")
                v_val = r.get("volume")
                if d_str and v_val is not None:
                    try:
                        fv = float(v_val)
                        if fv > 0:
                            vols_by_date_asset[(d_str, row_aid)] = fv
                    except (ValueError, TypeError):
                        pass

            if vols_by_date_asset:
                v_data: dict[str, list[float | None]] = {aid: [] for aid in final_assets}
                for d in clean_prices.index:
                    for aid in final_assets:
                        v_data[aid].append(vols_by_date_asset.get((d, aid)))
                raw_vdf = pd.DataFrame(v_data, index=clean_prices.index)
                raw_vdf.columns = display_tickers
                if not raw_vdf.dropna(how="all").empty:
                    # Align with returns index
                    volumes_df = raw_vdf.reindex(ret_df.index)
    except Exception:
        volumes_df = None

    return ret_df, display_tickers, volumes_df


def execute_vine_backtest(
    request: VineBacktestRequest,
    current_user: UserModel,
    db: Session,
) -> VineBacktestResponse:
    """Executes out-of-sample dynamic walk-forward Vine Tail Risk Parity backtesting."""
    min_obs = request.estimation_window + 10
    ret_df, tickers, volumes_df = _load_copula_returns_df(
        dataset_id=request.dataset_id,
        requested_tickers=request.tickers,
        current_user=current_user,
        db=db,
        start_date=request.start_date,
        end_date=request.end_date,
        min_observations=min_obs,
    )

    try:
        backtest_result = run_vine_tail_risk_parity_backtest(
            returns_df=ret_df,
            volumes_df=volumes_df,
            vine_type=request.vine_type,
            estimation_window=request.estimation_window,
            rebalance_frequency=request.rebalance_frequency,
            num_simulations=request.num_simulations,
            confidence_level=request.confidence_level,
            marginal_method=request.marginal_method,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            initial_capital=request.initial_capital,
            risk_free_rate=request.risk_free_rate,
            random_seed=request.random_seed,
            execution_model=request.execution_model,
            bid_ask_spread_bps=request.bid_ask_spread_bps,
            max_participation_rate=request.max_participation_rate,
            participation_policy=request.participation_policy,
            execution_horizon_days=request.execution_horizon_days,
            c_temp=request.c_temp,
            c_perm=request.c_perm,
            default_adv=request.default_adv,
            enable_endogenous_liquidity=request.enable_endogenous_liquidity,
            spread_stress_sensitivity=request.spread_stress_sensitivity,
            adv_stress_sensitivity=request.adv_stress_sensitivity,
            execution_scheduling_mode=request.execution_scheduling_mode,
            max_scheduling_days=request.max_scheduling_days,
            scheduling_risk_aversion=request.scheduling_risk_aversion,
            enable_regime_aware_execution=request.enable_regime_aware_execution,
            regime_num_states=request.regime_num_states,
            regime_adaptation_strength=request.regime_adaptation_strength,
            min_participation_rate=request.min_participation_rate,
        )

        return VineBacktestResponse(
            dataset_id=request.dataset_id,
            **backtest_result,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Vine backtest simulation failed: {str(exc)}",
        ) from exc

