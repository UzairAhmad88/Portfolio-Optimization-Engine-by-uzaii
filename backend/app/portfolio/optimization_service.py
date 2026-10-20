"""
Portfolio optimization and risk analytics service layer.

Coordinates dataset extraction, historical price alignment, statistical return
and covariance estimation, constraint resolution, numerical solver execution,
efficient frontier generation, and multi-portfolio comparison.
Integrates directly with the pure quantitative mathematics core.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.market_data.service import DatasetNotFoundError, get_dataset_rows
from app.portfolio.models import (
    AssetMetadata,
    EfficientFrontierRequest,
    EfficientFrontierResponse,
    FrontierPointModel,
    OptimizationRequest,
    OptimizationResponse,
    PortfolioComparisonItemModel,
    PortfolioComparisonRequest,
    PortfolioComparisonResponse,
    PortfolioDefinition,
    PortfolioMetricsModel,
    PortfolioRiskSummaryModel,
    SolverDiagnosticsModel,
)
from app.portfolio.service import (
    _build_quant_constraints,
    get_dataset_assets,
    validate_portfolio_definition,
)
from app.quant.constraints import validate_weights_against_constraints
from app.quant.covariance import covariance_matrix
from app.quant.optimization import (
    EfficientFrontierResult,
    FrontierPoint,
    OptimizationError,
    OptimizationObjective,
    OptimizationResult,
    OptimizationStatus,
    compute_equal_weight_baseline,
    generate_efficient_frontier,
    optimize_portfolio,
)
from app.quant.portfolio import (
    portfolio_returns,
    portfolio_variance,
    portfolio_volatility,
    summarize_weights,
)
from app.quant.returns import simple_returns
from app.quant.risk import annual_to_periodic_rate, portfolio_risk_summary


def _prepare_portfolio_market_data(
    portfolio: PortfolioDefinition,
    annualized: bool,
    periods_per_year: int,
    risk_free_rate: float,
) -> tuple[
    list[str] | None,
    dict[str, str] | None,
    pd.DataFrame | None,
    pd.DataFrame | None,
    pd.Series | None,
    pd.DataFrame | None,
    float,
    dict[str, Any],
    str,
    list[str],
    list[str],
]:
    """
    Validates portfolio definition, extracts authoritative historical prices,
    aligns trading days, and computes expected return vector and covariance matrix.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Multi-layer Portfolio Definition Validation
    validation_report = validate_portfolio_definition(portfolio)
    if not validation_report.is_valid:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            0.0,
            validation_report.date_coverage,
            "USD",
            validation_report.warnings,
            validation_report.errors,
        )

    # 2. Retrieve Raw Rows and Build Asset Lookup
    try:
        available_assets = get_dataset_assets(portfolio.dataset_id)
        raw_rows = get_dataset_rows(portfolio.dataset_id)
    except DatasetNotFoundError as exc:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            0.0,
            {},
            "USD",
            [],
            [str(exc)],
        )

    asset_by_id: dict[str, AssetMetadata] = {a.asset_id: a for a in available_assets}
    assets_by_ticker: dict[str, list[AssetMetadata]] = defaultdict(list)
    for a in available_assets:
        assets_by_ticker[a.ticker].append(a)

    resolved_asset_metadata: list[AssetMetadata] = []
    resolved_asset_ids: list[str] = []
    asset_id_map: dict[str, str] = {}

    for raw_sel in portfolio.assets:
        sel = str(raw_sel).strip().upper()
        if sel in asset_by_id:
            meta = asset_by_id[sel]
        elif sel in assets_by_ticker and len(assets_by_ticker[sel]) == 1:
            meta = assets_by_ticker[sel][0]
        else:
            errors.append(f"Unresolvable asset '{sel}'.")
            continue

        resolved_asset_metadata.append(meta)
        resolved_asset_ids.append(meta.asset_id)
        asset_id_map[meta.asset_id] = meta.asset_id
        asset_id_map[meta.ticker] = meta.asset_id

    if errors:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            0.0,
            {},
            "USD",
            warnings,
            errors,
        )

    currency = resolved_asset_metadata[0].currency if resolved_asset_metadata else "USD"

    # 3. Build Historical Price Matrix
    prices_by_date_asset: dict[tuple[str, str], float] = {}
    used_unadjusted: set[str] = set()

    for r in raw_rows:
        row_asset_id = f"{r['ticker']}:{r['market']}"
        if row_asset_id not in resolved_asset_ids:
            continue

        d_str = r.get("date")
        if not d_str:
            continue

        row_d = date.fromisoformat(d_str)
        if portfolio.start_date and row_d < portfolio.start_date:
            continue
        if portfolio.end_date and row_d > portfolio.end_date:
            continue

        p_val = r.get("adjusted_close")
        if p_val is not None and isinstance(p_val, (int, float)) and p_val > 0.0:
            price = float(p_val)
        else:
            price = float(r["close"])
            used_unadjusted.add(row_asset_id)

        prices_by_date_asset[(d_str, row_asset_id)] = price

    if used_unadjusted:
        warnings.append(
            f"Unadjusted close used for assets: {sorted(used_unadjusted)}; "
            "returns may be distorted by historical splits or dividend distributions."
        )

    all_dates = sorted({d for d, _ in prices_by_date_asset.keys()})
    price_data: dict[str, list[float | None]] = {aid: [] for aid in resolved_asset_ids}

    for d in all_dates:
        for aid in resolved_asset_ids:
            price_data[aid].append(prices_by_date_asset.get((d, aid)))

    raw_price_df = pd.DataFrame(price_data, index=all_dates)
    clean_price_df = raw_price_df.dropna(how="any").astype(float)
    common_obs_count = len(clean_price_df)

    date_coverage = {
        "requested_start_date": portfolio.start_date.isoformat() if portfolio.start_date else None,
        "requested_end_date": portfolio.end_date.isoformat() if portfolio.end_date else None,
        "effective_start_date": clean_price_df.index[0] if common_obs_count > 0 else None,
        "effective_end_date": clean_price_df.index[-1] if common_obs_count > 0 else None,
        "common_observation_count": common_obs_count,
    }

    if common_obs_count < 2:
        msg = (
            f"Selected assets share only {common_obs_count} common trading days. "
            "At least 2 synchronized price observations are required to compute returns."
        )
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            0.0,
            date_coverage,
            currency,
            warnings,
            [msg],
        )

    if common_obs_count < len(resolved_asset_ids) + 1:
        warnings.append(
            f"Observation count ({common_obs_count}) is small relative to asset count ({len(resolved_asset_ids)}). "
            "Sample covariance matrix may be rank-deficient or ill-conditioned."
        )

    # 4. Calculate Financial Returns and Covariance
    ret_df = simple_returns(clean_price_df).dropna(how="any").astype(float)
    if ret_df.empty:
        msg = "Return calculation produced zero valid aligned return rows."
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            0.0,
            date_coverage,
            currency,
            warnings,
            [msg],
        )

    mu_periodic = ret_df.mean()
    cov_periodic = covariance_matrix(ret_df, ddof=1, handle_na="drop_any", annualized=False)

    m = float(periods_per_year)
    if annualized:
        mu_calc = mu_periodic * m
        cov_calc = cov_periodic * m
        rf_calc = float(risk_free_rate)
    else:
        mu_calc = mu_periodic
        cov_calc = cov_periodic
        if risk_free_rate != 0.0:
            rf_calc = annual_to_periodic_rate(risk_free_rate, periods_per_year)
        else:
            rf_calc = 0.0

    return (
        resolved_asset_ids,
        asset_id_map,
        clean_price_df,
        ret_df,
        mu_calc,
        cov_calc,
        rf_calc,
        date_coverage,
        currency,
        warnings,
        [],
    )


def execute_portfolio_optimization(
    request: OptimizationRequest,
) -> OptimizationResponse:
    """
    Executes a complete, verified numerical portfolio optimization workflow:
    1. Validates portfolio definition, asset identity, currency, and pre-feasibility.
    2. Extracts and date-synchronizes historical prices for selected assets.
    3. Computes discrete simple returns, arithmetic mean returns, and covariance matrix.
    4. Applies explicit annualization conventions consistently across returns and covariance.
    5. Solves the configured objective (Minimum-Variance, Maximum-Sharpe, Equal-Weight, or Target-Return).
    6. Independently verifies constraint satisfaction and returns structured diagnostics.
    """
    portfolio = request.portfolio
    annualization_dict = {
        "annualized": request.annualized,
        "periods_per_year": request.periods_per_year,
        "risk_free_rate": request.risk_free_rate,
    }

    (
        resolved_asset_ids,
        asset_id_map,
        clean_price_df,
        ret_df,
        mu_calc,
        cov_calc,
        rf_calc,
        date_coverage,
        currency,
        prep_warnings,
        prep_errors,
    ) = _prepare_portfolio_market_data(
        portfolio=portfolio,
        annualized=request.annualized,
        periods_per_year=request.periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    if prep_errors or resolved_asset_ids is None or ret_df is None or mu_calc is None or cov_calc is None or asset_id_map is None:
        return OptimizationResponse(
            is_success=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            currency=currency,
            objective=request.objective,
            assets=portfolio.assets,
            weights={},
            metrics=None,
            is_feasible=False,
            constraint_violations=prep_errors,
            solver_diagnostics=SolverDiagnosticsModel(
                solver_name="Pre-Optimization Validator",
                status=OptimizationStatus.FAILED.value,
                message="; ".join(prep_errors),
                converged=False,
            ),
            annualization=annualization_dict,
            date_coverage=date_coverage,
            warnings=prep_warnings,
            errors=prep_errors,
        )

    quant_constraints = _build_quant_constraints(portfolio.constraints, asset_id_map)

    try:
        opt_res: OptimizationResult = optimize_portfolio(
            assets=resolved_asset_ids,
            cov_matrix=cov_calc,
            constraints=quant_constraints,
            objective=request.objective,
            expected_returns=mu_calc,
            target_return=request.target_return,
            risk_free_rate=rf_calc,
            annualized=request.annualized,
            periods_per_year=request.periods_per_year,
            observation_count=len(ret_df),
        )
    except OptimizationError as exc:
        return OptimizationResponse(
            is_success=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            currency=currency,
            objective=request.objective,
            assets=resolved_asset_ids,
            weights={},
            metrics=None,
            is_feasible=False,
            constraint_violations=[str(exc)],
            solver_diagnostics=SolverDiagnosticsModel(
                solver_name="Optimization Engine",
                status=OptimizationStatus.FAILED.value,
                message=str(exc),
                converged=False,
            ),
            annualization=annualization_dict,
            date_coverage=date_coverage,
            warnings=prep_warnings,
            errors=[str(exc)],
        )

    combined_warnings = list(dict.fromkeys(prep_warnings + opt_res.warnings))

    metrics_model: PortfolioMetricsModel | None = None
    if opt_res.is_feasible and opt_res.weights:
        w_arr = np.array([opt_res.weights.get(a, 0.0) for a in resolved_asset_ids], dtype=float)
        is_invested = bool(abs(opt_res.total_weight - 1.0) <= 1e-6)
        is_long = bool((w_arr >= -1e-12).all())
        has_short = bool((w_arr < -1e-12).any())

        metrics_model = PortfolioMetricsModel(
            expected_return=opt_res.expected_return,
            variance=opt_res.variance,
            volatility=opt_res.volatility,
            sharpe_ratio=opt_res.sharpe_ratio,
            total_weight=opt_res.total_weight,
            gross_exposure=opt_res.gross_exposure,
            is_fully_invested=is_invested,
            is_long_only=is_long,
            has_short_positions=has_short,
        )

    solver_diag = SolverDiagnosticsModel(
        solver_name=opt_res.solver_name,
        status=opt_res.solver_status.value,
        message=opt_res.solver_message,
        converged=opt_res.converged,
        iterations=opt_res.iterations,
        objective_value=opt_res.objective_value,
    )

    is_success = bool(opt_res.converged and opt_res.is_feasible)

    return OptimizationResponse(
        is_success=is_success,
        portfolio_name=portfolio.name,
        dataset_id=portfolio.dataset_id,
        currency=currency,
        objective=opt_res.objective,
        assets=opt_res.assets,
        weights=opt_res.weights,
        metrics=metrics_model,
        is_feasible=opt_res.is_feasible,
        constraint_violations=opt_res.constraint_violations,
        solver_diagnostics=solver_diag,
        annualization=annualization_dict,
        date_coverage=date_coverage,
        warnings=combined_warnings,
        errors=opt_res.constraint_violations if not is_success else [],
    )


def execute_efficient_frontier(
    request: EfficientFrontierRequest,
) -> EfficientFrontierResponse:
    """
    Computes the Markowitz risk-return curve and efficient frontier for a portfolio.
    """
    portfolio = request.portfolio
    annualization_dict = {
        "annualized": request.annualized,
        "periods_per_year": request.periods_per_year,
        "risk_free_rate": request.risk_free_rate,
    }

    (
        resolved_asset_ids,
        asset_id_map,
        clean_price_df,
        ret_df,
        mu_calc,
        cov_calc,
        rf_calc,
        date_coverage,
        currency,
        prep_warnings,
        prep_errors,
    ) = _prepare_portfolio_market_data(
        portfolio=portfolio,
        annualized=request.annualized,
        periods_per_year=request.periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    if prep_errors or resolved_asset_ids is None or ret_df is None or mu_calc is None or cov_calc is None or asset_id_map is None:
        return EfficientFrontierResponse(
            is_success=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            currency=currency,
            points=[],
            global_minimum_variance=None,
            requested_count=0,
            successful_count=0,
            failed_count=0,
            is_complete=False,
            min_feasible_return=None,
            max_feasible_return=None,
            annualization=annualization_dict,
            date_coverage=date_coverage,
            warnings=prep_warnings,
            errors=prep_errors,
        )

    quant_constraints = _build_quant_constraints(portfolio.constraints, asset_id_map)

    try:
        frontier_res: EfficientFrontierResult = generate_efficient_frontier(
            assets=resolved_asset_ids,
            cov_matrix=cov_calc,
            expected_returns=mu_calc,
            constraints=quant_constraints,
            target_returns=request.target_returns,
            target_count=request.target_count,
            risk_free_rate=rf_calc,
            annualized=request.annualized,
            periods_per_year=request.periods_per_year,
            observation_count=len(ret_df),
            currency=currency,
        )
    except OptimizationError as exc:
        return EfficientFrontierResponse(
            is_success=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            currency=currency,
            points=[],
            global_minimum_variance=None,
            requested_count=0,
            successful_count=0,
            failed_count=0,
            is_complete=False,
            min_feasible_return=None,
            max_feasible_return=None,
            annualization=annualization_dict,
            date_coverage=date_coverage,
            warnings=prep_warnings,
            errors=[str(exc)],
        )

    point_models: list[FrontierPointModel] = []
    for p in frontier_res.points:
        point_models.append(
            FrontierPointModel(
                target_return=p.target_return,
                actual_return=p.actual_return,
                variance=p.variance,
                volatility=p.volatility,
                sharpe_ratio=p.sharpe_ratio,
                weights=p.weights,
                is_feasible=p.is_feasible,
                status=p.status.value,
                classification=p.classification,  # type: ignore[arg-type]
                solver_message=p.solver_message,
                target_residual=p.target_residual,
                constraint_violations=p.constraint_violations,
                warnings=p.warnings,
            )
        )

    gmv_model: FrontierPointModel | None = None
    if frontier_res.global_minimum_variance is not None:
        gmv = frontier_res.global_minimum_variance
        gmv_model = FrontierPointModel(
            target_return=gmv.expected_return,
            actual_return=gmv.expected_return,
            variance=gmv.variance,
            volatility=gmv.volatility,
            sharpe_ratio=gmv.sharpe_ratio,
            weights=gmv.weights,
            is_feasible=gmv.is_feasible,
            status=gmv.solver_status.value,
            classification="efficient",
            solver_message=gmv.solver_message,
            target_residual=0.0,
            constraint_violations=gmv.constraint_violations,
            warnings=gmv.warnings,
        )

    all_warnings = list(dict.fromkeys(prep_warnings + frontier_res.warnings))
    is_success = frontier_res.successful_count > 0

    return EfficientFrontierResponse(
        is_success=is_success,
        portfolio_name=portfolio.name,
        dataset_id=portfolio.dataset_id,
        currency=currency,
        points=point_models,
        global_minimum_variance=gmv_model,
        requested_count=frontier_res.requested_count,
        successful_count=frontier_res.successful_count,
        failed_count=frontier_res.failed_count,
        is_complete=frontier_res.is_complete,
        min_feasible_return=frontier_res.min_feasible_return,
        max_feasible_return=frontier_res.max_feasible_return,
        annualization=annualization_dict,
        date_coverage=date_coverage,
        warnings=all_warnings,
        errors=[] if is_success else ["No feasible frontier points could be generated."],
    )


def execute_portfolio_comparison(
    request: PortfolioComparisonRequest,
) -> PortfolioComparisonResponse:
    """
    Executes consistent comparative risk and return analysis across multiple portfolio strategies
    (GMV, Maximum-Sharpe, Equal-Weight, Custom) on identical underlying market data.
    """
    portfolio = request.portfolio
    annualization_dict = {
        "annualized": request.annualized,
        "periods_per_year": request.periods_per_year,
        "risk_free_rate": request.risk_free_rate,
    }

    (
        resolved_asset_ids,
        asset_id_map,
        clean_price_df,
        ret_df,
        mu_calc,
        cov_calc,
        rf_calc,
        date_coverage,
        currency,
        prep_warnings,
        prep_errors,
    ) = _prepare_portfolio_market_data(
        portfolio=portfolio,
        annualized=request.annualized,
        periods_per_year=request.periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    if prep_errors or resolved_asset_ids is None or ret_df is None or mu_calc is None or cov_calc is None or asset_id_map is None:
        return PortfolioComparisonResponse(
            is_success=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            currency=currency,
            portfolios=[],
            annualization=annualization_dict,
            date_coverage=date_coverage,
            warnings=prep_warnings,
            errors=prep_errors,
        )

    quant_constraints = _build_quant_constraints(portfolio.constraints, asset_id_map)
    compared_portfolios: list[PortfolioComparisonItemModel] = []
    comparison_warnings: list[str] = list(prep_warnings)

    def _evaluate_candidate(name: str, opt_result: OptimizationResult) -> PortfolioComparisonItemModel:
        w_dict = opt_result.weights
        w_arr = np.array([w_dict.get(a, 0.0) for a in resolved_asset_ids], dtype=float)

        is_invested = bool(abs(opt_result.total_weight - 1.0) <= 1e-6)
        is_long = bool((w_arr >= -1e-12).all())
        has_short = bool((w_arr < -1e-12).any())

        metrics_model = PortfolioMetricsModel(
            expected_return=opt_result.expected_return,
            variance=opt_result.variance,
            volatility=opt_result.volatility,
            sharpe_ratio=opt_result.sharpe_ratio,
            total_weight=opt_result.total_weight,
            gross_exposure=opt_result.gross_exposure,
            is_fully_invested=is_invested,
            is_long_only=is_long,
            has_short_positions=has_short,
        )

        risk_summary_model: PortfolioRiskSummaryModel | None = None
        if opt_result.is_feasible and len(ret_df) >= 2:
            port_ret_series = portfolio_returns(returns=ret_df, weights=w_arr)
            rs = portfolio_risk_summary(
                returns=port_ret_series,
                risk_free_rate=rf_calc,
                required_return=rf_calc,
                periods_per_year=request.periods_per_year,
            )
            risk_summary_model = PortfolioRiskSummaryModel(
                arithmetic_mean_return=rs.mean_return_periodic,
                geometric_cumulative_return=rs.cumulative_return,
                annualized_return=rs.expected_return_annualized,
                periodic_volatility=rs.volatility_periodic,
                annualized_volatility=rs.volatility_annualized,
                variance=rs.variance_periodic,
                maximum_drawdown=abs(rs.max_drawdown),
                downside_deviation=rs.downside_deviation_annualized,
                sharpe_ratio=rs.sharpe_ratio,
                sortino_ratio=rs.sortino_ratio,
                mar_annualized=rs.mar_annual,
                risk_free_rate=rs.risk_free_rate_annual,
                observation_count=rs.observation_count,
                start_date=str(rs.start_date),
                end_date=str(rs.end_date),
                periods_per_year=rs.periods_per_year,
            )

        return PortfolioComparisonItemModel(
            name=name,
            weights=w_dict,
            metrics=metrics_model,
            risk_summary=risk_summary_model,
            is_feasible=opt_result.is_feasible,
        )

    # 1. Global Minimum Variance
    if request.include_gmv:
        gmv_res = optimize_portfolio(
            assets=resolved_asset_ids,
            cov_matrix=cov_calc,
            constraints=quant_constraints,
            objective=OptimizationObjective.MIN_VARIANCE,
            expected_returns=mu_calc,
            risk_free_rate=rf_calc,
            annualized=request.annualized,
            periods_per_year=request.periods_per_year,
            observation_count=len(ret_df),
        )
        if gmv_res.is_feasible:
            compared_portfolios.append(_evaluate_candidate("Global Minimum Variance", gmv_res))
        else:
            comparison_warnings.append(f"GMV portfolio optimization failed: {gmv_res.solver_message}")

    # 2. Maximum Sharpe Ratio
    if request.include_max_sharpe:
        try:
            ms_res = optimize_portfolio(
                assets=resolved_asset_ids,
                cov_matrix=cov_calc,
                constraints=quant_constraints,
                objective=OptimizationObjective.MAX_SHARPE,
                expected_returns=mu_calc,
                risk_free_rate=rf_calc,
                annualized=request.annualized,
                periods_per_year=request.periods_per_year,
                observation_count=len(ret_df),
            )
            if ms_res.is_feasible:
                compared_portfolios.append(_evaluate_candidate("Maximum Sharpe Ratio", ms_res))
            else:
                comparison_warnings.append(f"Maximum Sharpe portfolio optimization failed: {ms_res.solver_message}")
        except OptimizationError as exc:
            comparison_warnings.append(f"Maximum Sharpe portfolio could not be computed: {exc}")

    # 3. Equal Weight
    if request.include_equal_weight:
        ew_res = compute_equal_weight_baseline(
            assets=resolved_asset_ids,
            cov_matrix=cov_calc,
            constraints=quant_constraints,
            expected_returns=mu_calc,
            risk_free_rate=rf_calc,
            annualized=request.annualized,
            periods_per_year=request.periods_per_year,
            observation_count=len(ret_df),
        )
        compared_portfolios.append(_evaluate_candidate("Equal Weight", ew_res))

    # 4. Custom Portfolios
    for custom_name, custom_w in request.custom_portfolios.items():
        norm_custom_w: dict[str, float] = {}
        for k, v in custom_w.items():
            norm_k = asset_id_map.get(str(k).strip().upper(), str(k).strip().upper())
            norm_custom_w[norm_k] = float(v)

        w_arr = np.array([norm_custom_w.get(a, 0.0) for a in resolved_asset_ids], dtype=float)
        violations = validate_weights_against_constraints(norm_custom_w, resolved_asset_ids, quant_constraints)
        is_feas = len(violations) == 0

        var_val = float(portfolio_variance(w_arr, cov_calc))
        vol_val = float(portfolio_volatility(w_arr, cov_calc))
        exp_ret = float(w_arr @ mu_calc.to_numpy())
        sharpe = (exp_ret - rf_calc) / vol_val if vol_val > 1e-8 else None

        w_summary = summarize_weights(w_arr)
        custom_opt_res = OptimizationResult(
            objective="custom",
            assets=resolved_asset_ids,
            weights={resolved_asset_ids[i]: float(w_arr[i]) for i in range(len(resolved_asset_ids))},
            expected_return=exp_ret,
            variance=var_val,
            volatility=vol_val,
            sharpe_ratio=sharpe,
            total_weight=w_summary.total_weight,
            gross_exposure=w_summary.gross_exposure,
            is_feasible=is_feas,
            constraint_violations=violations,
            solver_name="Custom Allocation",
            solver_status=OptimizationStatus.CONVERGED if is_feas else OptimizationStatus.INVALID_FOR_CONSTRAINTS,
            solver_message="User-supplied portfolio allocation evaluated.",
            converged=True,
            objective_value=var_val,
            iterations=1,
            annualized=request.annualized,
            periods_per_year=request.periods_per_year,
            risk_free_rate=rf_calc,
            observation_count=len(ret_df),
        )
        compared_portfolios.append(_evaluate_candidate(custom_name, custom_opt_res))

    is_success = len(compared_portfolios) > 0
    return PortfolioComparisonResponse(
        is_success=is_success,
        portfolio_name=portfolio.name,
        dataset_id=portfolio.dataset_id,
        currency=currency,
        portfolios=compared_portfolios,
        annualization=annualization_dict,
        date_coverage=date_coverage,
        warnings=comparison_warnings,
        errors=[] if is_success else ["No valid portfolios could be compared."],
    )
