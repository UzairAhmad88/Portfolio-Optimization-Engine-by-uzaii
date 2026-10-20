"""
Orchestration service for Scenario Analysis, Stress Testing, and Sensitivity Analysis.
Connects dataset access validation, pure mathematical engines, and relational persistence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import json
import uuid
import numpy as np
import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.auth.dependencies import check_dataset_access
from app.db.models import ScenarioRunModel, UserModel
from app.market_data.service import DatasetNotFoundError, get_dataset_rows
from app.portfolio.models import AssetMetadata
from app.portfolio.service import get_dataset_assets
from app.quant.covariance import covariance_matrix
from app.quant.returns import simple_returns
from app.scenarios.models import (
    AssetShockContribution,
    ScenarioListItem,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioSummaryMetrics,
    SensitivityGridPoint,
    SensitivityRequest,
    SensitivityResponse,
)
from app.scenarios.sensitivity import evaluate_sensitivity_grid, generate_grid_values
from app.scenarios.shocks import apply_instantaneous_shocks
from app.scenarios.stress import extract_historical_window_shocks, stress_covariance_matrix


def prepare_scenario_data(
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
    assets_by_ticker: dict[str, list[AssetMetadata]] = defaultdict(list)
    for a in available_assets:
        assets_by_ticker[a.ticker].append(a)

    resolved_asset_ids: list[str] = []
    resolved_meta: list[AssetMetadata] = []
    ticker_to_id: dict[str, str] = {}

    for raw_sel in requested_assets:
        sel = str(raw_sel).strip().upper()
        if sel in asset_by_id:
            meta = asset_by_id[sel]
        elif sel in assets_by_ticker and len(assets_by_ticker[sel]) == 1:
            meta = assets_by_ticker[sel][0]
        else:
            raise ValueError(
                f"Asset '{raw_sel}' could not be uniquely resolved in dataset '{dataset_id}'."
            )
        resolved_asset_ids.append(meta.asset_id)
        resolved_meta.append(meta)
        ticker_to_id[meta.ticker] = meta.asset_id
        ticker_to_id[meta.asset_id] = meta.asset_id

    # 3. Currency homogeneity check
    currencies = {m.currency for m in resolved_meta}
    if len(currencies) > 1:
        raise ValueError(
            f"Multi-currency portfolios are not supported without explicit FX conversion: found {sorted(currencies)}."
        )
    currency = list(currencies)[0] if currencies else "USD"

    markets = {m.market for m in resolved_meta}
    periods_per_year = 250 if "PSX" in markets else 252

    warnings: list[str] = []

    # 4. Construct price matrix
    prices_by_date_asset: dict[tuple[str, str], float] = {}
    for r in raw_rows:
        row_asset_id = f"{r['ticker']}:{r['market']}"
        if row_asset_id not in resolved_asset_ids:
            continue
        d_str = r.get("date")
        if not d_str:
            continue
        # Prefer adjusted_close, fallback to close
        val = r.get("adjusted_close")
        if val is None:
            val = r.get("close")
        if val is not None:
            prices_by_date_asset[(d_str, row_asset_id)] = float(val)

    dates = sorted({d for d, _ in prices_by_date_asset.keys()})
    records: list[dict[str, float]] = []
    valid_dates: list[str] = []

    for d in dates:
        row_prices: dict[str, float] = {}
        all_present = True
        for a_id in resolved_asset_ids:
            p = prices_by_date_asset.get((d, a_id))
            if p is None:
                all_present = False
                break
            row_prices[a_id] = p
        if all_present:
            records.append(row_prices)
            valid_dates.append(d)

    if len(records) < 2:
        raise ValueError(
            f"Dataset '{dataset_id}' does not have sufficient overlapping trading dates for the selected assets."
        )

    price_df = pd.DataFrame(records, index=valid_dates)
    return price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id, warnings


def execute_scenario_analysis(
    req: ScenarioRequest,
    user: UserModel,
    session: Session,
) -> ScenarioResponse:
    """
    Executes an instantaneous shock, historical stress window, or covariance stress analysis.
    """
    price_df, resolved_asset_ids, currency, periods_per_year, ticker_to_id, warnings = prepare_scenario_data(
        req.dataset_id, req.assets, user, session
    )

    # Map user weights (which may use ticker or asset_id) to canonical composite IDs
    canonical_weights: dict[str, float] = {}
    for a in resolved_asset_ids:
        ticker = a.split(":")[0]
        w = req.weights.get(a, req.weights.get(ticker, 0.0))
        canonical_weights[a] = float(w)

    total_w = sum(canonical_weights.values())
    if total_w > 1.000001:
        raise ValueError(f"Sum of asset weights ({total_w:.6f}) exceeds 1.0.")

    # Calculate baseline returns and covariance matrix
    ret_df = simple_returns(price_df)
    cov_df = covariance_matrix(ret_df, annualized=True, periods_per_year=periods_per_year)

    baseline_vol = None
    stressed_vol = None
    vol_change = None

    # Calculate baseline volatility
    try:
        w_vec = np.array([canonical_weights[a] for a in resolved_asset_ids], dtype=np.float64)
        cov_np = cov_df.to_numpy(dtype=np.float64)
        base_var = float(w_vec @ cov_np @ w_vec)
        baseline_vol = float(np.sqrt(max(0.0, base_var)))
    except Exception:
        pass

    resolved_shocks: dict[str, float] = {}

    if req.scenario_type == "custom_asset_shock":
        raw_shocks = req.asset_shocks or {}
        for a in resolved_asset_ids:
            ticker = a.split(":")[0]
            s = raw_shocks.get(a, raw_shocks.get(ticker, 0.0))
            resolved_shocks[a] = float(s)

    elif req.scenario_type == "historical_window":
        hist_shocks, eff_start, eff_end, hist_warn = extract_historical_window_shocks(
            price_df, req.historical_start_date, req.historical_end_date
        )
        resolved_shocks = hist_shocks
        warnings.extend(hist_warn)

    elif req.scenario_type == "covariance_stress":
        # Stressed covariance
        stressed_cov_df, b_vol, s_vol, v_change, cov_warn = stress_covariance_matrix(
            cov_df,
            canonical_weights,
            volatility_multiplier=req.volatility_multiplier,
            correlation_multiplier=req.correlation_multiplier,
            auto_project_psd=req.auto_project_psd,
        )
        baseline_vol = b_vol
        stressed_vol = s_vol
        vol_change = v_change
        warnings.extend(cov_warn)

        # Asset price shocks can also be supplied during covariance stress, or default to 0.0
        raw_shocks = req.asset_shocks or {}
        for a in resolved_asset_ids:
            ticker = a.split(":")[0]
            s = raw_shocks.get(a, raw_shocks.get(ticker, 0.0))
            resolved_shocks[a] = float(s)

    else:
        raise ValueError(f"Unsupported scenario type: '{req.scenario_type}'")

    # Apply instantaneous valuation shocks
    metrics, contributions = apply_instantaneous_shocks(
        weights=canonical_weights,
        shocks=resolved_shocks,
        initial_capital=req.initial_capital,
        currency=currency,
    )

    if baseline_vol is not None:
        metrics.baseline_volatility = round(baseline_vol, 6)
    if stressed_vol is not None:
        metrics.stressed_volatility = round(stressed_vol, 6)
    if vol_change is not None:
        metrics.volatility_change = round(vol_change, 6)

    run_id = str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).isoformat()

    # Persist in relational database
    try:
        run_record = ScenarioRunModel(
            id=run_id,
            user_id=user.id if user else None,
            dataset_id=req.dataset_id,
            name=req.name,
            scenario_type=req.scenario_type,
            initial_capital=req.initial_capital,
            percentage_change=metrics.percentage_change,
            absolute_change=metrics.absolute_change,
            currency=currency,
            status="completed",
            request_config_json=json.dumps(req.model_dump()),
            summary_metrics_json=json.dumps(metrics.model_dump()),
            contributions_json=json.dumps([c.model_dump() for c in contributions]),
            warnings_json=json.dumps(warnings),
        )
        session.add(run_record)
        session.commit()
    except Exception:
        session.rollback()
        # Non-fatal to response generation if database storage is unavailable

    return ScenarioResponse(
        id=run_id,
        dataset_id=req.dataset_id,
        name=req.name,
        scenario_type=req.scenario_type,
        status="completed",
        created_at=now_str,
        metrics=metrics,
        contributions=contributions,
        warnings=warnings,
        is_hypothetical=True,
    )


def execute_sensitivity_analysis(
    req: SensitivityRequest,
    user: UserModel,
    session: Session,
) -> SensitivityResponse:
    """
    Executes a 1-factor or 2-factor parametric sensitivity sweep.
    """
    price_df, resolved_asset_ids, currency, _, ticker_to_id, warnings = prepare_scenario_data(
        req.dataset_id, req.assets, user, session
    )

    canonical_weights: dict[str, float] = {}
    for a in resolved_asset_ids:
        ticker = a.split(":")[0]
        w = req.weights.get(a, req.weights.get(ticker, 0.0))
        canonical_weights[a] = float(w)

    f1_id = ticker_to_id.get(req.factor_1_asset.strip().upper(), req.factor_1_asset)
    if f1_id not in resolved_asset_ids:
        raise ValueError(f"Factor 1 asset '{req.factor_1_asset}' is not in the portfolio asset list.")

    f1_shocks = generate_grid_values(req.factor_1_min_shock, req.factor_1_max_shock, req.factor_1_steps)

    f2_id = None
    f2_shocks = None
    if req.factor_2_asset:
        f2_id = ticker_to_id.get(req.factor_2_asset.strip().upper(), req.factor_2_asset)
        if f2_id not in resolved_asset_ids:
            raise ValueError(f"Factor 2 asset '{req.factor_2_asset}' is not in the portfolio asset list.")
        min_2 = req.factor_2_min_shock if req.factor_2_min_shock is not None else -0.30
        max_2 = req.factor_2_max_shock if req.factor_2_max_shock is not None else 0.30
        steps_2 = req.factor_2_steps if req.factor_2_steps is not None else 7

        total_grid_size = len(f1_shocks) * steps_2
        if total_grid_size > 441:
            raise ValueError(f"2D sensitivity grid size ({total_grid_size}) exceeds limit of 441 points.")

        f2_shocks = generate_grid_values(min_2, max_2, steps_2)

    grid = evaluate_sensitivity_grid(
        weights=canonical_weights,
        initial_capital=req.initial_capital,
        factor_1_asset=f1_id,
        factor_1_shocks=f1_shocks,
        factor_2_asset=f2_id,
        factor_2_shocks=f2_shocks,
    )

    return SensitivityResponse(
        id=str(uuid.uuid4()),
        dataset_id=req.dataset_id,
        name=req.name,
        factor_1_asset=f1_id,
        factor_2_asset=f2_id,
        grid=grid,
        baseline_portfolio_value=req.initial_capital,
        currency=currency,
        warnings=warnings,
        is_hypothetical=True,
    )


def list_scenario_runs(
    session: Session,
    user: UserModel,
    dataset_id: str | None = None,
) -> list[ScenarioListItem]:
    """
    Lists saved scenario analysis runs for the authenticated researcher.
    """
    query = session.query(ScenarioRunModel).filter(ScenarioRunModel.user_id == user.id)
    if dataset_id:
        query = query.filter(ScenarioRunModel.dataset_id == dataset_id)

    runs = query.order_by(desc(ScenarioRunModel.created_at)).limit(50).all()

    return [
        ScenarioListItem(
            id=r.id,
            dataset_id=r.dataset_id,
            user_id=r.user_id,
            name=r.name,
            scenario_type=r.scenario_type,
            percentage_change=r.percentage_change,
            absolute_change=r.absolute_change,
            currency=r.currency,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in runs
    ]


def get_scenario_run(
    session: Session,
    scenario_id: str,
    user: UserModel,
) -> ScenarioResponse:
    """
    Retrieves full scenario details with strict tenant isolation.
    """
    run = session.query(ScenarioRunModel).filter(ScenarioRunModel.id == scenario_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Scenario run not found.")

    if run.user_id and run.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=404, detail="Scenario run not found.")

    metrics_dict = run.get_summary_metrics()
    contributions_raw = run.get_contributions()
    warnings = run.get_warnings()

    return ScenarioResponse(
        id=run.id,
        dataset_id=run.dataset_id,
        name=run.name,
        scenario_type=run.scenario_type,
        status=run.status,
        created_at=run.created_at.isoformat() if run.created_at else "",
        metrics=ScenarioSummaryMetrics(**metrics_dict),
        contributions=[AssetShockContribution(**c) for c in contributions_raw],
        warnings=warnings,
        is_hypothetical=True,
    )


def delete_scenario_run(
    session: Session,
    scenario_id: str,
    user: UserModel,
) -> dict[str, str]:
    """
    Deletes a saved scenario run with strict tenant isolation.
    """
    run = session.query(ScenarioRunModel).filter(ScenarioRunModel.id == scenario_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Scenario run not found.")

    if run.user_id and run.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=404, detail="Scenario run not found.")

    session.delete(run)
    session.commit()
    return {"message": "Scenario run deleted successfully.", "id": scenario_id}
