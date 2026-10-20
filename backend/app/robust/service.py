"""
Service orchestration for robust portfolio optimization, parameter sensitivity,
and out-of-sample historical validation.
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
from app.quant.constraints import InvestmentConstraints
from app.quant.covariance import covariance_matrix
from app.quant.returns import simple_returns
from app.quant.robust_optimization import (
    CovarianceShrinkageConfig,
    CovarianceShrinkageTarget,
    ExpectedReturnUncertaintyConfig,
    RobustObjective,
    UncertaintyModelType,
    optimize_robust_portfolio,
    run_constraint_sensitivity_sweep,
)
from app.robust.models import (
    PortfolioWeightItem,
    RobustBacktestRequest,
    RobustBacktestResponse,
    RobustConstraintsRequest,
    RobustOptimizationRequest,
    RobustOptimizationResponse,
    SensitivityAnalysisRequest,
    SensitivityAnalysisResponse,
    SensitivityPointResponse,
)


def _build_constraints(req: RobustConstraintsRequest) -> InvestmentConstraints:
    return InvestmentConstraints(
        default_min_weight=req.default_min_weight,
        default_max_weight=req.default_max_weight,
        target_total_weight=req.target_total_weight,
        allow_short=req.allow_short,
        max_gross_exposure=req.max_gross_exposure,
    )


def _build_uncertainty_config(req) -> ExpectedReturnUncertaintyConfig:
    m = req.model.lower()
    if m == "box":
        model_type = UncertaintyModelType.BOX
    elif m == "ellipsoidal":
        model_type = UncertaintyModelType.ELLIPSOIDAL
    else:
        model_type = UncertaintyModelType.NONE

    return ExpectedReturnUncertaintyConfig(
        model=model_type,
        confidence_level=req.confidence_level,
        absolute_radius=req.absolute_radius,
    )


def _build_shrinkage_config(req) -> CovarianceShrinkageConfig:
    t = req.target.lower()
    if t == "diagonal":
        target_type = CovarianceShrinkageTarget.DIAGONAL
    elif t == "scaled_identity":
        target_type = CovarianceShrinkageTarget.SCALED_IDENTITY
    elif t == "constant_correlation":
        target_type = CovarianceShrinkageTarget.CONSTANT_CORRELATION
    else:
        target_type = CovarianceShrinkageTarget.NONE

    return CovarianceShrinkageConfig(
        target=target_type,
        intensity=req.intensity,
    )


def execute_robust_optimization(
    request: RobustOptimizationRequest,
    current_user: UserModel,
    session: Session,
) -> RobustOptimizationResponse:
    """
    Executes baseline vs robust optimization over historical market data.
    """
    start_d = date.fromisoformat(request.start_date) if request.start_date else None
    end_d = date.fromisoformat(request.end_date) if request.end_date else None

    # Prepare historical price matrix
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=start_d,
        end_date=end_d,
        user=current_user,
        session=session,
        min_required_observations=len(request.assets) + 2,
    )

    # Compute daily discrete returns
    ret_df = simple_returns(clean_prices)
    obs_count = len(ret_df)

    # Annualized sample expected returns and covariance matrix
    ret_series = ret_df.mean() * float(periods_per_year)
    cov_df = covariance_matrix(
        ret_df,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )

    constraints = _build_constraints(request.constraints)
    uncertainty_config = _build_uncertainty_config(request.uncertainty)
    shrinkage_config = _build_shrinkage_config(request.shrinkage)

    obj_str = request.objective.lower()
    if obj_str == "min_variance":
        obj_enum = RobustObjective.MIN_VARIANCE
    elif obj_str == "mean_variance_utility":
        obj_enum = RobustObjective.MEAN_VARIANCE_UTILITY
    else:
        obj_enum = RobustObjective.MAX_SHARPE

    robust_res = optimize_robust_portfolio(
        assets=resolved_assets,
        expected_returns=ret_series,
        cov_matrix=cov_df,
        constraints=constraints,
        objective=obj_enum,
        uncertainty_config=uncertainty_config,
        shrinkage_config=shrinkage_config,
        risk_free_rate=request.risk_free_rate,
        risk_aversion=request.risk_aversion,
        annualized=True,
        periods_per_year=periods_per_year,
        observation_count=obs_count,
    )

    # Formulate weight items
    weight_items: list[PortfolioWeightItem] = []
    for a in resolved_assets:
        w_b = float(robust_res.baseline_result.weights.get(a, 0.0))
        w_r = float(robust_res.robust_result.weights.get(a, 0.0))
        weight_items.append(
            PortfolioWeightItem(
                asset_id=a,
                baseline_weight=w_b,
                robust_weight=w_r,
                weight_difference=float(w_r - w_b),
                nominal_return=float(ret_series.get(a, 0.0)),
                worst_case_return=float(robust_res.worst_case_return_vector.get(a, 0.0)),
                uncertainty_radius=float(robust_res.uncertainty_radius_vector.get(a, 0.0)),
            )
        )

    # Baseline metrics
    b_eval = robust_res.baseline_result
    baseline_metrics = {
        "expected_return": b_eval.expected_return,
        "variance": b_eval.variance,
        "volatility": b_eval.volatility,
        "sharpe_ratio": b_eval.sharpe_ratio,
        "total_weight": b_eval.total_weight,
        "gross_exposure": b_eval.gross_exposure,
        "is_feasible": b_eval.is_feasible,
        "solver_status": b_eval.solver_status.value,
        "objective_value": b_eval.objective_value,
        "iterations": b_eval.iterations,
    }

    # Robust metrics
    r_eval = robust_res.robust_result
    robust_metrics = {
        "nominal_expected_return": robust_res.nominal_expected_return_robust,
        "worst_case_expected_return": robust_res.worst_case_expected_return_robust,
        "nominal_volatility": robust_res.nominal_volatility_robust,
        "shrunk_volatility": robust_res.shrunk_volatility_robust,
        "nominal_sharpe_ratio": (
            (robust_res.nominal_expected_return_robust - request.risk_free_rate)
            / max(robust_res.nominal_volatility_robust, 1e-8)
            if robust_res.nominal_volatility_robust > 1e-8
            else None
        ),
        "worst_case_sharpe_ratio": (
            (robust_res.worst_case_expected_return_robust - request.risk_free_rate)
            / max(robust_res.shrunk_volatility_robust, 1e-8)
            if robust_res.shrunk_volatility_robust > 1e-8
            else None
        ),
        "total_weight": r_eval.total_weight,
        "gross_exposure": r_eval.gross_exposure,
        "is_feasible": r_eval.is_feasible,
        "solver_status": r_eval.solver_status.value,
        "objective_value": r_eval.objective_value,
        "iterations": r_eval.iterations,
    }

    diagnostics = {
        "weight_distance_d1": robust_res.weight_distance_d1,
        "max_weight_shift": robust_res.max_weight_shift,
        "turnover_from_baseline": robust_res.turnover_from_baseline,
        "baseline_hhi": robust_res.baseline_hhi,
        "robust_hhi": robust_res.robust_hhi,
        "effective_assets_baseline": robust_res.effective_assets_baseline,
        "effective_assets_robust": robust_res.effective_assets_robust,
        "uncertainty_applied": robust_res.uncertainty_applied,
        "shrinkage_applied": robust_res.shrinkage_applied,
        "observation_count": obs_count,
        "currency": currency,
        "periods_per_year": periods_per_year,
    }

    return RobustOptimizationResponse(
        objective=request.objective,
        dataset_id=request.dataset_id,
        assets=resolved_assets,
        weights=weight_items,
        baseline_weights=b_eval.weights,
        robust_weights=r_eval.weights,
        baseline_metrics=baseline_metrics,
        robust_metrics=robust_metrics,
        diagnostics=diagnostics,
        shrunk_covariance=robust_res.shrunk_covariance_matrix,
        is_feasible=robust_res.is_feasible,
        solver_status=r_eval.solver_status.value,
        solver_message=r_eval.solver_message,
        warnings=warnings + robust_res.warnings,
    )


def execute_sensitivity_sweep(
    request: SensitivityAnalysisRequest,
    current_user: UserModel,
    session: Session,
) -> SensitivityAnalysisResponse:
    """
    Executes a bounded parameter sensitivity sweep over constraints or uncertainty parameters.
    """
    start_d = date.fromisoformat(request.start_date) if request.start_date else None
    end_d = date.fromisoformat(request.end_date) if request.end_date else None

    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=start_d,
        end_date=end_d,
        user=current_user,
        session=session,
        min_required_observations=len(request.assets) + 2,
    )

    ret_df = simple_returns(clean_prices)
    obs_count = len(ret_df)
    ret_series = ret_df.mean() * float(periods_per_year)
    cov_df = covariance_matrix(
        ret_df,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )

    constraints = _build_constraints(request.constraints)
    uncertainty_config = _build_uncertainty_config(request.uncertainty)
    shrinkage_config = _build_shrinkage_config(request.shrinkage)

    obj_str = request.objective.lower()
    if obj_str == "min_variance":
        obj_enum = RobustObjective.MIN_VARIANCE
    elif obj_str == "mean_variance_utility":
        obj_enum = RobustObjective.MEAN_VARIANCE_UTILITY
    else:
        obj_enum = RobustObjective.MAX_SHARPE

    sweep_res = run_constraint_sensitivity_sweep(
        assets=resolved_assets,
        expected_returns=ret_series,
        cov_matrix=cov_df,
        constraints=constraints,
        parameter_to_sweep=request.parameter_to_sweep,
        grid_min=request.grid_min,
        grid_max=request.grid_max,
        num_steps=request.num_steps,
        objective=obj_enum,
        uncertainty_config=uncertainty_config,
        shrinkage_config=shrinkage_config,
        risk_free_rate=request.risk_free_rate,
        annualized=True,
        periods_per_year=periods_per_year,
        observation_count=obs_count,
    )

    point_responses = [
        SensitivityPointResponse(
            parameter_value=p.parameter_value,
            parameter_label=p.parameter_label,
            is_feasible=p.is_feasible,
            solver_status=p.solver_status,
            weights=p.weights,
            nominal_expected_return=p.nominal_expected_return,
            worst_case_expected_return=p.worst_case_expected_return,
            volatility=p.volatility,
            sharpe_ratio=p.sharpe_ratio,
            weight_distance_d1=p.weight_distance_d1,
            hhi=p.hhi,
            effective_assets=p.effective_assets,
            binding_constraints=p.binding_constraints,
        )
        for p in sweep_res.points
    ]

    return SensitivityAnalysisResponse(
        parameter_name=sweep_res.parameter_name,
        parameter_description=sweep_res.parameter_description,
        baseline_value=sweep_res.baseline_value,
        points=point_responses,
        total_evaluations=sweep_res.total_evaluations,
        feasible_evaluations=sweep_res.feasible_evaluations,
        infeasible_evaluations=sweep_res.infeasible_evaluations,
        warnings=warnings + sweep_res.warnings,
    )


def execute_robust_backtest(
    request: RobustBacktestRequest,
    current_user: UserModel,
    session: Session,
) -> RobustBacktestResponse:
    """
    Executes out-of-sample backtest comparing baseline vs robust portfolio
    with zero look-ahead bias across strictly non-overlapping windows.
    """
    # 1. Retrieve full historical price panel
    clean_prices, resolved_assets, currency, periods_per_year, warnings = prepare_backtest_data(
        dataset_id=request.dataset_id,
        requested_assets=request.assets,
        start_date=None,
        end_date=None,
        user=current_user,
        session=session,
        min_required_observations=len(request.assets) + 10,
    )

    # 2. Partition into training (in-sample) and test (out-of-sample)
    split_date = request.train_end_date
    df_train = clean_prices[clean_prices.index <= split_date]
    df_test = clean_prices[clean_prices.index >= split_date]

    if len(df_train) < len(resolved_assets) + 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Training period before {split_date} has only {len(df_train)} bars; "
                f"requires at least {len(resolved_assets) + 2} observations."
            ),
        )
    if len(df_test) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Out-of-sample test period after {split_date} has only {len(df_test)} bars; "
                "requires at least 5 observations."
            ),
        )

    # 3. Compute estimates on training window only
    ret_train = simple_returns(df_train)
    ret_series_train = ret_train.mean() * float(periods_per_year)
    cov_df_train = covariance_matrix(
        ret_train,
        ddof=1,
        handle_na="drop_any",
        annualized=True,
        periods_per_year=periods_per_year,
    )

    constraints = _build_constraints(request.constraints)
    uncertainty_config = _build_uncertainty_config(request.uncertainty)
    shrinkage_config = _build_shrinkage_config(request.shrinkage)

    obj_str = request.objective.lower()
    if obj_str == "min_variance":
        obj_enum = RobustObjective.MIN_VARIANCE
    elif obj_str == "mean_variance_utility":
        obj_enum = RobustObjective.MEAN_VARIANCE_UTILITY
    else:
        obj_enum = RobustObjective.MAX_SHARPE

    # Solve baseline and robust portfolios on training data
    robust_opt = optimize_robust_portfolio(
        assets=resolved_assets,
        expected_returns=ret_series_train,
        cov_matrix=cov_df_train,
        constraints=constraints,
        objective=obj_enum,
        uncertainty_config=uncertainty_config,
        shrinkage_config=shrinkage_config,
        risk_free_rate=request.risk_free_rate,
        annualized=True,
        periods_per_year=periods_per_year,
        observation_count=len(ret_train),
    )

    w_base = robust_opt.baseline_result.weights
    w_robust = robust_opt.robust_result.weights

    # 4. Simulate out-of-sample performance on test window
    base_metrics, base_equity, _ = run_portfolio_simulation(
        prices=df_test,
        strategy_type="target_weights",
        target_weights=w_base,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=100_000.0,
        transaction_cost_bps=request.cost_bps,
        slippage_bps=request.slippage_bps,
        periods_per_year=periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    rob_metrics, rob_equity, _ = run_portfolio_simulation(
        prices=df_test,
        strategy_type="target_weights",
        target_weights=w_robust,
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=100_000.0,
        transaction_cost_bps=request.cost_bps,
        slippage_bps=request.slippage_bps,
        periods_per_year=periods_per_year,
        risk_free_rate=request.risk_free_rate,
    )

    # Downsample curves if test series is long (> 100 points)
    n_pts = len(base_equity)
    stride = max(1, n_pts // 80)
    merged_curves: list[dict[str, Any]] = []

    for i in range(0, n_pts, stride):
        pt_b = base_equity[i]
        pt_r = rob_equity[i]
        merged_curves.append(
            {
                "date": pt_b.date,
                "baseline_portfolio_value": pt_b.portfolio_value_net,
                "robust_portfolio_value": pt_r.portfolio_value_net,
                "baseline_drawdown": pt_b.drawdown_net,
                "robust_drawdown": pt_r.drawdown_net,
            }
        )

    # Ensure last point is included
    if merged_curves[-1]["date"] != base_equity[-1].date:
        pt_b = base_equity[-1]
        pt_r = rob_equity[-1]
        merged_curves.append(
            {
                "date": pt_b.date,
                "baseline_portfolio_value": pt_b.portfolio_value_net,
                "robust_portfolio_value": pt_r.portfolio_value_net,
                "baseline_drawdown": pt_b.drawdown_net,
                "robust_drawdown": pt_r.drawdown_net,
            }
        )

    return RobustBacktestResponse(
        dataset_id=request.dataset_id,
        assets=resolved_assets,
        train_period={"start": str(df_train.index[0]), "end": str(df_train.index[-1])},
        test_period={"start": str(df_test.index[0]), "end": str(df_test.index[-1])},
        baseline_weights=w_base,
        robust_weights=w_robust,
        weight_distance_d1=robust_opt.weight_distance_d1,
        baseline_kpis={
            "cumulative_return": base_metrics.cumulative_return_net,
            "annualized_return": base_metrics.annualized_return_net,
            "annualized_volatility": base_metrics.volatility_annualized_net,
            "sharpe_ratio": base_metrics.sharpe_ratio_net,
            "max_drawdown": base_metrics.max_drawdown_net,
            "total_turnover": base_metrics.total_turnover,
            "total_cost_drag": base_metrics.total_friction_costs,
            "final_portfolio_value": base_metrics.final_value_net,
        },
        robust_kpis={
            "cumulative_return": rob_metrics.cumulative_return_net,
            "annualized_return": rob_metrics.annualized_return_net,
            "annualized_volatility": rob_metrics.volatility_annualized_net,
            "sharpe_ratio": rob_metrics.sharpe_ratio_net,
            "max_drawdown": rob_metrics.max_drawdown_net,
            "total_turnover": rob_metrics.total_turnover,
            "total_cost_drag": rob_metrics.total_friction_costs,
            "final_portfolio_value": rob_metrics.final_value_net,
        },
        out_of_sample_comparison={
            "delta_cumulative_return": float(
                rob_metrics.cumulative_return_net - base_metrics.cumulative_return_net
            ),
            "delta_volatility": float(
                rob_metrics.volatility_annualized_net - base_metrics.volatility_annualized_net
            ),
            "delta_sharpe": (
                float(rob_metrics.sharpe_ratio_net - base_metrics.sharpe_ratio_net)
                if rob_metrics.sharpe_ratio_net is not None and base_metrics.sharpe_ratio_net is not None
                else None
            ),
            "delta_max_drawdown": float(
                rob_metrics.max_drawdown_net - base_metrics.max_drawdown_net
            ),
        },
        equity_curves=merged_curves,
        warnings=warnings + robust_opt.warnings,
    )
