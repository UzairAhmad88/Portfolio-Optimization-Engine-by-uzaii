"""
Performance attribution and benchmark comparison service orchestrator.
Handles dataset verification, price extraction, metric computation, and persistence.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import check_dataset_access
from app.db.models import BacktestRunModel, DatasetModel, PerformanceReportModel, UserModel
from app.market_data.service import get_dataset_rows
from app.performance.models import (
    AssetContribution,
    PerformanceAnalysisRequest,
    PerformanceReportListItem,
    PerformanceResponse,
    PerformanceSummaryMetrics,
    PerformanceTimeseriesPoint,
)
from app.quant.performance import (
    align_return_series,
    calculate_multi_period_contributions,
    evaluate_comparative_performance,
)
from app.quant.risk import drawdown_series


def _extract_asset_prices_df(
    dataset_rows: list[dict[str, Any]],
    requested_assets: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Extracts aligned daily price matrix for requested assets from dataset rows.
    Returns (prices_df, warnings).
    """
    warnings: list[str] = []
    asset_norm_map: dict[str, str] = {}
    for a in requested_assets:
        clean_a = a.strip().upper()
        asset_norm_map[clean_a] = clean_a
        if ":" in clean_a:
            ticker = clean_a.split(":")[0]
            asset_norm_map[ticker] = clean_a

    record_list: list[dict[str, Any]] = []
    for r in dataset_rows:
        t = str(r.get("ticker", "")).strip().upper()
        aid = str(r.get("asset_id") or f"{t}:{r.get('market', 'US')}").strip().upper()

        matched_key = None
        if aid in asset_norm_map:
            matched_key = asset_norm_map[aid]
        elif t in asset_norm_map:
            matched_key = asset_norm_map[t]

        if matched_key:
            record_list.append({
                "date": str(r.get("date")),
                "asset": matched_key,
                "price": float(r.get("adjusted_close") or r.get("close") or 0.0),
            })

    if not record_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"None of the requested assets {requested_assets} were found in the dataset."]},
        )

    df_raw = pd.DataFrame(record_list)
    pivoted = df_raw.pivot(index="date", columns="asset", values="price").sort_index()

    missing = [a for a in requested_assets if a not in pivoted.columns]
    if missing:
        warnings.append(f"Assets {missing} had no matching price bars in dataset.")

    pivoted = pivoted.dropna()
    if pivoted.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": ["Zero overlapping historical trading dates across requested assets."]},
        )

    return pivoted, warnings


def _extract_single_asset_series(
    dataset_rows: list[dict[str, Any]],
    target_asset: str,
) -> pd.Series:
    """
    Extracts daily price series for a single benchmark asset.
    Matches either exact asset_id ('SPY:US') or ticker ('SPY').
    """
    clean_target = target_asset.strip().upper()
    target_ticker = clean_target.split(":")[0] if ":" in clean_target else clean_target

    matched_records: list[dict[str, Any]] = []
    for r in dataset_rows:
        t = str(r.get("ticker", "")).strip().upper()
        aid = str(r.get("asset_id") or f"{t}:{r.get('market', 'US')}").strip().upper()

        if aid == clean_target or t == clean_target or t == target_ticker:
            matched_records.append({
                "date": str(r.get("date")),
                "price": float(r.get("adjusted_close") or r.get("close") or 0.0),
            })

    if not matched_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Benchmark asset '{target_asset}' not found in the dataset."]},
        )

    df_b = pd.DataFrame(matched_records).drop_duplicates(subset=["date"]).sort_values("date")
    series_b = pd.Series(df_b["price"].values, index=df_b["date"].values, dtype=float)
    return series_b


def execute_performance_analysis(
    req: PerformanceAnalysisRequest,
    user: UserModel,
    db: Session,
) -> PerformanceResponse:
    """
    Orchestrates portfolio performance attribution and benchmark evaluation.
    """
    # 1. Enforce dataset ownership / tenant access
    check_dataset_access(db, req.dataset_id, user)

    dataset_rows = get_dataset_rows(req.dataset_id)
    if not dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Dataset '{req.dataset_id}' contains no price bars."]},
        )

    warnings: list[str] = []
    portfolio_returns_series: pd.Series
    holdings_weights: dict[str, float] = {}
    constituent_prices_df: pd.DataFrame | None = None

    # 2. Extract Portfolio Return Series
    if req.backtest_id:
        # Evaluate from saved backtest run
        backtest = (
            db.query(BacktestRunModel)
            .filter(BacktestRunModel.id == req.backtest_id)
            .first()
        )
        if not backtest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errors": [f"Backtest run '{req.backtest_id}' not found."]},
            )
        if backtest.user_id != user.id and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"errors": [f"Backtest run '{req.backtest_id}' not found."]},
            )

        equity_curve = backtest.get_equity_curve()
        if not equity_curve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": ["Backtest contains no equity curve time-series data."]},
            )

        df_eq = pd.DataFrame(equity_curve)
        # Use return_net as authoritative realized performance
        portfolio_returns_series = pd.Series(
            df_eq["return_net"].values,
            index=df_eq["date"].values,
            dtype=float,
        )

        strat_cfg = backtest.get_strategy_config()
        if strat_cfg and "weights" in strat_cfg and strat_cfg["weights"]:
            holdings_weights = strat_cfg["weights"]
        elif strat_cfg and "assets" in strat_cfg and strat_cfg["assets"]:
            n_assets = len(strat_cfg["assets"])
            holdings_weights = {a: 1.0 / n_assets for a in strat_cfg["assets"]}

        # Attempt to load constituent prices for contribution analysis
        if holdings_weights:
            try:
                constituent_prices_df, w_warn = _extract_asset_prices_df(dataset_rows, list(holdings_weights.keys()))
                warnings.extend(w_warn)
            except Exception:
                constituent_prices_df = None
    else:
        # Evaluate from custom asset weights and dataset historical returns
        assert req.assets is not None and req.weights is not None
        holdings_weights = req.weights
        constituent_prices_df, w_warn = _extract_asset_prices_df(dataset_rows, req.assets)
        warnings.extend(w_warn)

        ret_df = constituent_prices_df.pct_change().dropna()
        weights_series = pd.Series(holdings_weights).reindex(ret_df.columns).fillna(0.0)
        portfolio_returns_series = (ret_df * weights_series).sum(axis=1)

    # 3. Extract Benchmark Return Series
    bench_price_series = _extract_single_asset_series(dataset_rows, req.benchmark_asset)
    benchmark_returns_series = bench_price_series.pct_change().dropna()

    # 4. Optional Date Truncation
    if req.start_date:
        start_str = str(req.start_date)
        portfolio_returns_series = portfolio_returns_series[portfolio_returns_series.index >= start_str]
        benchmark_returns_series = benchmark_returns_series[benchmark_returns_series.index >= start_str]
    if req.end_date:
        end_str = str(req.end_date)
        portfolio_returns_series = portfolio_returns_series[portfolio_returns_series.index <= end_str]
        benchmark_returns_series = benchmark_returns_series[benchmark_returns_series.index <= end_str]

    # 5. Synchronize via exact date inner join
    try:
        p_aligned, b_aligned = align_return_series(portfolio_returns_series, benchmark_returns_series)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": [str(e)]},
        )

    # 6. Evaluate Comparative Metrics
    comp_metrics = evaluate_comparative_performance(
        p_aligned,
        b_aligned,
        risk_free_rate_annual=req.risk_free_rate,
        periods_per_year=252,
    )

    # 7. Asset-Level Contribution Analysis
    contributions: list[AssetContribution] = []
    if constituent_prices_df is not None and holdings_weights:
        # Align constituent prices with the evaluated date window
        aligned_const_prices = constituent_prices_df.reindex(index=p_aligned.index).dropna()
        if not aligned_const_prices.empty and len(aligned_const_prices) > 1:
            const_returns = aligned_const_prices.pct_change().dropna()
            try:
                linked_contributions = calculate_multi_period_contributions(const_returns, holdings_weights)
                port_cum_ret = comp_metrics.portfolio_cumulative_return
                for asset_name, c_val in linked_contributions.items():
                    asset_cum = float(np.prod(1.0 + const_returns[asset_name]) - 1.0)
                    share = (c_val / port_cum_ret) if abs(port_cum_ret) > 1e-12 else 0.0
                    contributions.append(
                        AssetContribution(
                            asset=asset_name,
                            weight=float(holdings_weights.get(asset_name, 0.0)),
                            cumulative_return=asset_cum,
                            total_contribution=c_val,
                            share_of_return=share,
                        )
                    )
            except Exception as e:
                warnings.append(f"Multi-period asset contribution calculation skipped: {str(e)}")

    # 8. Time-Series Trajectory Construction
    p_cum_series = np.cumprod(1.0 + p_aligned) - 1.0
    b_cum_series = np.cumprod(1.0 + b_aligned) - 1.0
    a_cum_series = p_cum_series - b_cum_series

    p_dd = drawdown_series(p_aligned)
    b_dd = drawdown_series(b_aligned)

    timeseries_points: list[PerformanceTimeseriesPoint] = []
    # If observation count is large (> 500), downsample to prevent UI sluggishness
    step = max(1, len(p_aligned) // 250) if len(p_aligned) > 500 else 1
    selected_indices = list(range(0, len(p_aligned), step))
    if (len(p_aligned) - 1) not in selected_indices:
        selected_indices.append(len(p_aligned) - 1)

    for idx in selected_indices:
        dt = str(p_aligned.index[idx])
        timeseries_points.append(
            PerformanceTimeseriesPoint(
                date=dt,
                portfolio_return=float(p_aligned.iloc[idx]),
                benchmark_return=float(b_aligned.iloc[idx]),
                active_return=float(p_aligned.iloc[idx] - b_aligned.iloc[idx]),
                portfolio_cumulative=float(p_cum_series.iloc[idx]),
                benchmark_cumulative=float(b_cum_series.iloc[idx]),
                active_cumulative=float(a_cum_series.iloc[idx]),
                drawdown_portfolio=float(p_dd.iloc[idx]),
                drawdown_benchmark=float(b_dd.iloc[idx]),
            )
        )

    summary_model = PerformanceSummaryMetrics(
        observation_count=comp_metrics.observation_count,
        periods_per_year=comp_metrics.periods_per_year,
        start_date=comp_metrics.start_date,
        end_date=comp_metrics.end_date,
        portfolio_cumulative_return=comp_metrics.portfolio_cumulative_return,
        portfolio_annualized_return=comp_metrics.portfolio_annualized_return,
        portfolio_annualized_volatility=comp_metrics.portfolio_annualized_volatility,
        portfolio_sharpe_ratio=comp_metrics.portfolio_sharpe_ratio,
        portfolio_sortino_ratio=comp_metrics.portfolio_sortino_ratio,
        portfolio_max_drawdown=comp_metrics.portfolio_max_drawdown,
        benchmark_cumulative_return=comp_metrics.benchmark_cumulative_return,
        benchmark_annualized_return=comp_metrics.benchmark_annualized_return,
        benchmark_annualized_volatility=comp_metrics.benchmark_annualized_volatility,
        benchmark_sharpe_ratio=comp_metrics.benchmark_sharpe_ratio,
        benchmark_sortino_ratio=comp_metrics.benchmark_sortino_ratio,
        benchmark_max_drawdown=comp_metrics.benchmark_max_drawdown,
        arithmetic_active_return=comp_metrics.arithmetic_active_return,
        geometric_excess_return=comp_metrics.geometric_excess_return,
        annualized_active_return=comp_metrics.annualized_active_return,
        tracking_error=comp_metrics.tracking_error,
        information_ratio=comp_metrics.information_ratio,
        beta=comp_metrics.beta,
        alpha_annualized=comp_metrics.alpha_annualized,
        treynor_ratio=comp_metrics.treynor_ratio,
        up_capture_ratio=comp_metrics.up_capture_ratio,
        down_capture_ratio=comp_metrics.down_capture_ratio,
    )

    report_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # 9. Relational Persistence
    if req.save_report:
        report_record = PerformanceReportModel(
            id=report_id,
            user_id=user.id,
            dataset_id=req.dataset_id,
            backtest_id=req.backtest_id,
            name=req.name,
            benchmark_asset=req.benchmark_asset,
            risk_free_rate=req.risk_free_rate,
            start_date=datetime.strptime(comp_metrics.start_date, "%Y-%m-%d").date() if comp_metrics.start_date else None,
            end_date=datetime.strptime(comp_metrics.end_date, "%Y-%m-%d").date() if comp_metrics.end_date else None,
            status="completed",
            metrics_json=json.dumps(summary_model.model_dump()),
            contributions_json=json.dumps([c.model_dump() for c in contributions]),
            timeseries_json=json.dumps([t.model_dump() for t in timeseries_points]),
            warnings_json=json.dumps(warnings),
        )
        db.add(report_record)
        db.commit()

    return PerformanceResponse(
        id=report_id,
        name=req.name,
        dataset_id=req.dataset_id,
        backtest_id=req.backtest_id,
        benchmark_asset=req.benchmark_asset,
        risk_free_rate=req.risk_free_rate,
        start_date=comp_metrics.start_date,
        end_date=comp_metrics.end_date,
        status="completed",
        metrics=summary_model,
        contributions=contributions,
        timeseries=timeseries_points,
        warnings=warnings,
        is_hypothetical=True,
        disclaimer=(
            "Performance attribution and benchmark comparison metrics are historical research diagnostics. "
            "They do not guarantee future profitability or constitute investment recommendations."
        ),
        created_at=created_at,
    )


def list_performance_reports(
    user: UserModel,
    db: Session,
) -> list[PerformanceReportListItem]:
    """Lists saved performance reports owned by the authenticated user."""
    query = db.query(PerformanceReportModel)
    if user.role != "admin":
        query = query.filter(PerformanceReportModel.user_id == user.id)

    records = query.order_by(PerformanceReportModel.created_at.desc()).all()
    results: list[PerformanceReportListItem] = []

    for r in records:
        metrics = r.get_metrics()
        results.append(
            PerformanceReportListItem(
                id=r.id,
                name=r.name,
                dataset_id=r.dataset_id,
                backtest_id=r.backtest_id,
                benchmark_asset=r.benchmark_asset,
                portfolio_cumulative_return=float(metrics.get("portfolio_cumulative_return", 0.0)),
                benchmark_cumulative_return=float(metrics.get("benchmark_cumulative_return", 0.0)),
                arithmetic_active_return=float(metrics.get("arithmetic_active_return", 0.0)),
                information_ratio=metrics.get("information_ratio"),
                beta=metrics.get("beta"),
                alpha_annualized=metrics.get("alpha_annualized"),
                status=r.status,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
        )
    return results


def get_performance_report(
    report_id: str,
    user: UserModel,
    db: Session,
) -> PerformanceResponse:
    """Retrieves an owned performance report by ID."""
    report = (
        db.query(PerformanceReportModel)
        .filter(PerformanceReportModel.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Performance report '{report_id}' not found."]},
        )
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Performance report '{report_id}' not found."]},
        )

    metrics_raw = report.get_metrics()
    contributions_raw = report.get_contributions()
    timeseries_raw = report.get_timeseries()
    warnings = report.get_warnings()

    return PerformanceResponse(
        id=report.id,
        name=report.name,
        dataset_id=report.dataset_id,
        backtest_id=report.backtest_id,
        benchmark_asset=report.benchmark_asset,
        risk_free_rate=report.risk_free_rate,
        start_date=str(report.start_date) if report.start_date else None,
        end_date=str(report.end_date) if report.end_date else None,
        status=report.status,
        metrics=PerformanceSummaryMetrics(**metrics_raw),
        contributions=[AssetContribution(**c) for c in contributions_raw],
        timeseries=[PerformanceTimeseriesPoint(**t) for t in timeseries_raw],
        warnings=warnings,
        is_hypothetical=True,
        disclaimer=(
            "Performance attribution and benchmark comparison metrics are historical research diagnostics. "
            "They do not guarantee future profitability or constitute investment recommendations."
        ),
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


def delete_performance_report(
    report_id: str,
    user: UserModel,
    db: Session,
) -> None:
    """Deletes an owned performance report by ID."""
    report = (
        db.query(PerformanceReportModel)
        .filter(PerformanceReportModel.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Performance report '{report_id}' not found."]},
        )
    if report.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": [f"Performance report '{report_id}' not found."]},
        )

    db.delete(report)
    db.commit()
