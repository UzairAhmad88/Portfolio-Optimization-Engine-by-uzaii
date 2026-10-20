"""
Application service for Monte Carlo portfolio risk simulation and probabilistic risk analysis.
Handles tenant isolation, data preparation, calculation orchestration, and relational persistence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import secrets
import uuid

from fastapi import HTTPException
import numpy as np
import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.db.models import RiskSimulationRunModel, UserModel
from app.market_data.service import DatasetNotFoundError, get_dataset_rows
from app.portfolio.models import AssetMetadata
from app.portfolio.service import get_dataset_assets
from app.quant.covariance import covariance_matrix
from app.quant.returns import simple_returns
from app.quant.var_cvar import (
    calculate_empirical_var_cvar,
    historical_var_cvar,
    parametric_var_cvar,
)
from app.risk_simulation.engine import (
    compute_distribution_histogram,
    downsample_trajectories,
    generate_multivariate_returns,
    simulate_portfolio_wealth,
)
from app.risk_simulation.models import (
    DistributionBin,
    MultiEstimatorComparison,
    RiskSimulationListItem,
    RiskSimulationRequest,
    RiskSimulationResponse,
    RiskSimulationSummary,
    SimulationPathPoint,
    VaRCVaREstimate,
    VaRCVaRStandaloneRequest,
)


def prepare_simulation_data(
    dataset_id: str,
    requested_assets: list[str],
    user: UserModel,
    session: Session,
) -> tuple[pd.DataFrame, list[str], str, int, dict[str, str], list[str]]:
    """
    Validates dataset access, resolves assets to canonical IDs (TICKER:MARKET),
    checks currency homogeneity, and builds a synchronized price DataFrame.

    Returns:
        tuple of (price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id_map, warnings).
    """
    # 1. Authorization check
    check_dataset_access(session, dataset_id, user)

    # 2. Retrieve assets & rows
    available_assets = get_dataset_assets(dataset_id)
    raw_rows = get_dataset_rows(dataset_id)

    asset_by_id: dict[str, AssetMetadata] = {a.asset_id: a for a in available_assets}
    ticker_to_id_map: dict[str, str] = {}
    for a in available_assets:
        ticker_to_id_map[a.ticker] = a.asset_id
        ticker_to_id_map[a.asset_id] = a.asset_id

    # Resolve requested assets
    resolved_asset_ids: list[str] = []
    missing_assets: list[str] = []
    for ra in requested_assets:
        canon_id = ticker_to_id_map.get(ra)
        if canon_id and canon_id in asset_by_id:
            if canon_id not in resolved_asset_ids:
                resolved_asset_ids.append(canon_id)
        else:
            missing_assets.append(ra)

    if missing_assets:
        raise HTTPException(
            status_code=422,
            detail=f"Requested assets not found in dataset {dataset_id}: {missing_assets}",
        )

    # 3. Currency homogeneity check
    currencies: set[str] = {asset_by_id[aid].currency for aid in resolved_asset_ids}
    if len(currencies) > 1:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Multi-currency portfolios are not permitted without FX conversion. "
                f"Found currencies: {sorted(currencies)}"
            ),
        )
    currency = currencies.pop() if currencies else "USD"

    # Periods per year convention
    sample_asset = asset_by_id[resolved_asset_ids[0]]
    periods_per_year = 250 if sample_asset.market.upper() == "PSX" else 252

    # 4. Build synchronized price DataFrame
    asset_date_prices: dict[str, dict[str, float]] = defaultdict(dict)
    for r in raw_rows:
        ticker = r.get("ticker")
        market = r.get("market")
        cid = f"{ticker}:{market}"
        if cid in asset_by_id and cid in resolved_asset_ids:
            dt_val = r.get("date")
            dt_str = dt_val.isoformat() if hasattr(dt_val, "isoformat") else str(dt_val)
            price = r.get("adjusted_close")
            if price is None:
                price = r.get("close")
            if price is not None:
                asset_date_prices[cid][dt_str] = float(price)

    common_dates: set[str] | None = None
    for aid in resolved_asset_ids:
        dates_for_asset = set(asset_date_prices[aid].keys())
        if common_dates is None:
            common_dates = dates_for_asset
        else:
            common_dates = common_dates.intersection(dates_for_asset)

    if not common_dates or len(common_dates) < 5:
        raise HTTPException(
            status_code=422,
            detail="Insufficient overlapping historical price observations across requested assets (need >= 5 bars).",
        )

    sorted_dates = sorted(common_dates)
    price_dict: dict[str, list[float]] = {}
    for aid in resolved_asset_ids:
        price_dict[aid] = [asset_date_prices[aid][d] for d in sorted_dates]

    price_df = pd.DataFrame(price_dict, index=sorted_dates)
    warnings: list[str] = []
    return price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id_map, warnings


def execute_risk_simulation(
    req: RiskSimulationRequest,
    user: UserModel,
    session: Session,
) -> RiskSimulationResponse:
    """
    Executes a Monte Carlo portfolio risk simulation, calculates VaR and CVaR,
    compiles multi-estimator comparisons, and persists the run.
    """
    # 1. Prepare data & validate assets
    price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id_map, prep_warnings = (
        prepare_simulation_data(req.dataset_id, req.assets, user, session)
    )

    # 2. Resolve weights
    weights_arr = np.zeros(len(resolved_asset_ids), dtype=float)
    for i, aid in enumerate(resolved_asset_ids):
        # Check both canonical ID and ticker in req.weights
        w = req.weights.get(aid)
        if w is None:
            # Fallback to ticker
            ticker = aid.split(":")[0]
            w = req.weights.get(ticker, 0.0)
        weights_arr[i] = float(w)

    sum_weights = float(np.sum(weights_arr))
    if sum_weights <= 0.0:
        raise HTTPException(status_code=422, detail="Sum of asset weights must be strictly positive.")
    if sum_weights > 1.0 + 1e-6:
        raise HTTPException(status_code=422, detail=f"Sum of asset weights ({sum_weights:.4f}) exceeds 1.0.")

    # 3. Compute returns and covariance
    returns_df = simple_returns(price_df)
    clean_returns = returns_df.dropna()
    if len(clean_returns) < 5:
        raise HTTPException(status_code=422, detail="Insufficient clean historical returns for covariance estimation.")

    # Empirical mean returns & sample covariance
    hist_means = clean_returns.mean().to_numpy(dtype=float)
    hist_cov = covariance_matrix(clean_returns, ddof=1).to_numpy(dtype=float)

    # Apply custom expected returns if provided
    mean_vector = np.copy(hist_means)
    if req.custom_expected_returns:
        for i, aid in enumerate(resolved_asset_ids):
            ticker = aid.split(":")[0]
            if aid in req.custom_expected_returns:
                mean_vector[i] = float(req.custom_expected_returns[aid])
            elif ticker in req.custom_expected_returns:
                mean_vector[i] = float(req.custom_expected_returns[ticker])

    # 4. Seed selection
    seed = req.seed if req.seed is not None else secrets.randbelow(2147483647)

    # 5. Run Monte Carlo simulation
    sim_returns, sim_warnings = generate_multivariate_returns(
        mean_vector=mean_vector,
        cov_matrix=hist_cov,
        horizon_days=req.horizon_days,
        num_paths=req.num_paths,
        seed=seed,
        distribution=req.distribution,
        degrees_of_freedom=req.degrees_of_freedom,
    )
    all_warnings = prep_warnings + sim_warnings

    # 6. Compound wealth
    wealth_paths = simulate_portfolio_wealth(
        initial_capital=req.initial_capital,
        asset_weights=weights_arr,
        simulated_returns=sim_returns,
        rebalance_policy=req.rebalance_policy,
    )

    terminal_values = wealth_paths[:, -1]
    terminal_losses = req.initial_capital - terminal_values
    terminal_returns = (terminal_values - req.initial_capital) / req.initial_capital

    # 7. Summary metrics
    expected_terminal_val = float(np.mean(terminal_values))
    median_terminal_val = float(np.median(terminal_values))
    expected_terminal_ret = float(np.mean(terminal_returns))
    term_ret_vol = float(np.std(terminal_returns, ddof=1)) if len(terminal_returns) > 1 else 0.0

    quantiles_dict = {
        "p1": float(np.percentile(terminal_values, 1)),
        "p5": float(np.percentile(terminal_values, 5)),
        "p10": float(np.percentile(terminal_values, 10)),
        "p25": float(np.percentile(terminal_values, 25)),
        "p50": median_terminal_val,
        "p75": float(np.percentile(terminal_values, 75)),
        "p90": float(np.percentile(terminal_values, 90)),
        "p95": float(np.percentile(terminal_values, 95)),
        "p99": float(np.percentile(terminal_values, 99)),
    }

    prob_neg_ret = float(np.mean(terminal_values < req.initial_capital))

    prob_exceed_thresh: float | None = None
    if req.loss_threshold is not None:
        prob_exceed_thresh = float(np.mean(terminal_losses > req.loss_threshold))

    # 8. VaR and CVaR calculations across confidence levels
    var_cvar_metrics: list[VaRCVaREstimate] = []
    estimator_comparisons: list[MultiEstimatorComparison] = []

    # Historical portfolio periodic return series for benchmark estimators
    hist_port_returns = clean_returns.to_numpy(dtype=float) @ weights_arr
    port_periodic_mean = float(np.mean(hist_port_returns))
    port_periodic_vol = float(np.std(hist_port_returns, ddof=1))

    for conf in sorted(set(req.confidence_levels)):
        # Monte Carlo empirical estimate
        mc_res = calculate_empirical_var_cvar(
            terminal_losses=terminal_losses,
            initial_capital=req.initial_capital,
            confidence_level=conf,
        )
        var_cvar_metrics.append(
            VaRCVaREstimate(
                confidence_level=conf,
                var_absolute=mc_res.var_absolute,
                var_percentage=mc_res.var_percentage,
                cvar_absolute=mc_res.cvar_absolute,
                cvar_percentage=mc_res.cvar_percentage,
            )
        )

        # Parametric analytical estimate
        param_res = parametric_var_cvar(
            initial_capital=req.initial_capital,
            periodic_mean_return=port_periodic_mean,
            periodic_volatility=port_periodic_vol,
            horizon_periods=req.horizon_days,
            confidence_level=conf,
        )

        # Historical empirical estimate (if historical sample size permits)
        hist_var_abs: float | None = None
        hist_cvar_abs: float | None = None
        if len(hist_port_returns) >= req.horizon_days:
            try:
                hist_res = historical_var_cvar(
                    historical_portfolio_returns=hist_port_returns,
                    initial_capital=req.initial_capital,
                    horizon_periods=req.horizon_days,
                    confidence_level=conf,
                )
                hist_var_abs = hist_res.var_absolute
                hist_cvar_abs = hist_res.cvar_absolute
            except Exception:
                pass

        estimator_comparisons.append(
            MultiEstimatorComparison(
                confidence_level=conf,
                monte_carlo_var=mc_res.var_absolute,
                monte_carlo_cvar=mc_res.cvar_absolute,
                parametric_var=param_res.var_absolute,
                parametric_cvar=param_res.cvar_absolute,
                historical_var=hist_var_abs,
                historical_cvar=hist_cvar_abs,
            )
        )

    # 9. Histogram & Trajectory
    distribution_bins = compute_distribution_histogram(terminal_returns, num_bins=30)
    trajectory = downsample_trajectories(wealth_paths, max_sample_paths=25)

    summary = RiskSimulationSummary(
        initial_capital=req.initial_capital,
        expected_terminal_value=expected_terminal_val,
        median_terminal_value=median_terminal_val,
        expected_terminal_return=expected_terminal_ret,
        terminal_return_volatility=term_ret_vol,
        terminal_quantiles=quantiles_dict,
        prob_negative_return=prob_neg_ret,
        prob_exceed_threshold=prob_exceed_thresh,
        min_terminal_value=float(np.min(terminal_values)),
        max_terminal_value=float(np.max(terminal_values)),
        var_cvar_metrics=var_cvar_metrics,
        estimator_comparisons=estimator_comparisons,
        currency=currency,
    )

    # 10. Relational persistence
    run_id = f"sim-{uuid.uuid4()}"
    now_utc = datetime.now(timezone.utc)

    # Find 95% metrics for top-level indexing
    var_95_val = next((m.var_absolute for m in var_cvar_metrics if abs(m.confidence_level - 0.95) < 1e-4), var_cvar_metrics[0].var_absolute if var_cvar_metrics else 0.0)
    cvar_95_val = next((m.cvar_absolute for m in var_cvar_metrics if abs(m.confidence_level - 0.95) < 1e-4), var_cvar_metrics[0].cvar_absolute if var_cvar_metrics else 0.0)

    req_dump = req.model_dump(mode="json")
    req_dump["seed"] = seed

    db_record = RiskSimulationRunModel(
        id=run_id,
        user_id=user.id,
        dataset_id=req.dataset_id,
        name=req.name,
        distribution=req.distribution.value,
        rebalance_policy=req.rebalance_policy.value,
        horizon_days=req.horizon_days,
        num_paths=req.num_paths,
        initial_capital=req.initial_capital,
        expected_terminal_return=expected_terminal_ret,
        var_95=var_95_val,
        cvar_95=cvar_95_val,
        currency=currency,
        status="completed",
        request_config_json=json.dumps(req_dump),
        summary_metrics_json=json.dumps(summary.model_dump(mode="json")),
        distribution_bins_json=json.dumps([b.model_dump(mode="json") for b in distribution_bins]),
        trajectory_json=json.dumps([t.model_dump(mode="json") for t in trajectory]),
        warnings_json=json.dumps(all_warnings),
        created_at=now_utc,
    )
    session.add(db_record)
    session.commit()

    return RiskSimulationResponse(
        id=run_id,
        dataset_id=req.dataset_id,
        name=req.name,
        distribution=req.distribution.value,
        rebalance_policy=req.rebalance_policy.value,
        horizon_days=req.horizon_days,
        num_paths=req.num_paths,
        seed=seed,
        summary=summary,
        distribution_bins=distribution_bins,
        trajectory=trajectory,
        warnings=all_warnings,
        is_hypothetical=True,
        created_at=now_utc.isoformat(),
    )


def calculate_standalone_var_cvar(
    req: VaRCVaRStandaloneRequest,
    user: UserModel,
    session: Session,
) -> list[MultiEstimatorComparison]:
    """
    Computes standalone Parametric and Historical VaR and CVaR for quick analysis.
    """
    price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id_map, warnings = (
        prepare_simulation_data(req.dataset_id, req.assets, user, session)
    )

    weights_arr = np.zeros(len(resolved_asset_ids), dtype=float)
    for i, aid in enumerate(resolved_asset_ids):
        ticker = aid.split(":")[0]
        w = req.weights.get(aid, req.weights.get(ticker, 0.0))
        weights_arr[i] = float(w)

    clean_returns = simple_returns(price_df).dropna()
    hist_port_returns = clean_returns.to_numpy(dtype=float) @ weights_arr
    port_periodic_mean = float(np.mean(hist_port_returns))
    port_periodic_vol = float(np.std(hist_port_returns, ddof=1))

    comparisons: list[MultiEstimatorComparison] = []
    for conf in sorted(set(req.confidence_levels)):
        param_res = parametric_var_cvar(
            initial_capital=req.initial_capital,
            periodic_mean_return=port_periodic_mean,
            periodic_volatility=port_periodic_vol,
            horizon_periods=req.horizon_days,
            confidence_level=conf,
        )

        hist_var_abs: float | None = None
        hist_cvar_abs: float | None = None
        if len(hist_port_returns) >= req.horizon_days:
            try:
                hist_res = historical_var_cvar(
                    historical_portfolio_returns=hist_port_returns,
                    initial_capital=req.initial_capital,
                    horizon_periods=req.horizon_days,
                    confidence_level=conf,
                )
                hist_var_abs = hist_res.var_absolute
                hist_cvar_abs = hist_res.cvar_absolute
            except Exception:
                pass

        comparisons.append(
            MultiEstimatorComparison(
                confidence_level=conf,
                monte_carlo_var=param_res.var_absolute,  # fallback for standalone
                monte_carlo_cvar=param_res.cvar_absolute,
                parametric_var=param_res.var_absolute,
                parametric_cvar=param_res.cvar_absolute,
                historical_var=hist_var_abs,
                historical_cvar=hist_cvar_abs,
            )
        )

    return comparisons


def list_risk_simulations(
    user: UserModel,
    session: Session,
    limit: int = 50,
    offset: int = 0,
) -> list[RiskSimulationListItem]:
    """Lists saved risk simulations owned by the authenticated user."""
    query = (
        session.query(RiskSimulationRunModel)
        .filter(RiskSimulationRunModel.user_id == user.id)
        .order_by(desc(RiskSimulationRunModel.created_at))
        .offset(offset)
        .limit(limit)
    )
    records = query.all()
    results: list[RiskSimulationListItem] = []
    for r in records:
        dt_str = r.created_at.isoformat() if r.created_at else ""
        results.append(
            RiskSimulationListItem(
                id=r.id,
                dataset_id=r.dataset_id,
                user_id=r.user_id,
                name=r.name,
                distribution=r.distribution,
                horizon_days=r.horizon_days,
                num_paths=r.num_paths,
                expected_terminal_return=r.expected_terminal_return,
                var_95=r.var_95,
                cvar_95=r.cvar_95,
                currency=r.currency,
                created_at=dt_str,
            )
        )
    return results


def get_risk_simulation(
    run_id: str,
    user: UserModel,
    session: Session,
) -> RiskSimulationResponse:
    """Retrieves a specific simulation run owned by the authenticated user."""
    record = (
        session.query(RiskSimulationRunModel)
        .filter(RiskSimulationRunModel.id == run_id)
        .first()
    )
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail=f"Risk simulation run {run_id} not found.")

    raw_req = record.get_request_config()
    raw_summary = record.get_summary_metrics()
    raw_bins = record.get_distribution_bins()
    raw_trajectory = record.get_trajectory()
    warnings = record.get_warnings()

    summary = RiskSimulationSummary(**raw_summary)
    bins = [DistributionBin(**b) for b in raw_bins]
    trajectory = [SimulationPathPoint(**t) for t in raw_trajectory]

    return RiskSimulationResponse(
        id=record.id,
        dataset_id=record.dataset_id,
        name=record.name,
        distribution=record.distribution,
        rebalance_policy=record.rebalance_policy,
        horizon_days=record.horizon_days,
        num_paths=record.num_paths,
        seed=int(raw_req["seed"]) if raw_req.get("seed") is not None else 0,
        summary=summary,
        distribution_bins=bins,
        trajectory=trajectory,
        warnings=warnings,
        is_hypothetical=True,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


def delete_risk_simulation(
    run_id: str,
    user: UserModel,
    session: Session,
) -> dict[str, str]:
    """Deletes an owned risk simulation run."""
    record = (
        session.query(RiskSimulationRunModel)
        .filter(RiskSimulationRunModel.id == run_id)
        .first()
    )
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail=f"Risk simulation run {run_id} not found.")

    session.delete(record)
    session.commit()
    return {"status": "success", "message": f"Risk simulation run {run_id} deleted."}
