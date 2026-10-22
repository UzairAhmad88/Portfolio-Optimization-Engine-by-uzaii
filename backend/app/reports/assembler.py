"""
Analytical assembler and aggregation service for Stage 34 institutional reporting.
Transforms authorized database records (BacktestRunModel, PerformanceReportModel,
ResearchExperimentModel, DatasetSnapshotModel) into canonical Gate A domain report payloads.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    BacktestRunModel,
    DatasetModel,
    DatasetSnapshotModel,
    PerformanceReportModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.market_data.service import get_dataset_rows
from app.performance.service import _extract_single_asset_series
from app.quant.performance import (
    align_return_series,
    calculate_capture_ratios,
    calculate_jensens_alpha,
    calculate_multi_period_contributions,
    calculate_treynor_ratio,
    evaluate_comparative_performance,
)
from app.quant.risk import drawdown_series
from app.reports.contracts import (
    AssetAllocationItem,
    BenchmarkRelativeMetrics,
    CommonReportEnvelope,
    ExecutiveKPIs,
    FrictionAndExecutionMetrics,
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    MonthlyReturnCell,
    ReportWarning,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
    StrategyMandate,
    TimeSeriesPoint,
)
from app.research.overfitting_models import OverfittingDiagnosticsRequest
from app.research.service import ResearchService

logger = logging.getLogger(__name__)


class ReportAssemblerService:
    """
    Core aggregation and assembly service for institutional strategy and research reporting.
    """

    @classmethod
    def assemble_fact_sheet(
        cls,
        backtest_id: str,
        current_user: UserModel,
        db: Session,
        benchmark_asset: str | None = None,
    ) -> StrategyFactSheetPayload:
        """
        Compiles the 1-Page Strategy Fact Sheet payload for an authorized backtest.
        """
        backtest = cls._get_authorized_backtest(backtest_id, current_user, db)
        envelope, warnings = cls._assemble_envelope(
            report_type="fact_sheet",
            backtest=backtest,
            current_user=current_user,
            db=db,
        )

        mandate = cls._assemble_mandate(backtest)
        equity_curve_data = backtest.get_equity_curve()
        summary_metrics = backtest.get_summary_metrics()

        # Benchmarks
        benchmark_metrics, bm_series, bm_warn = cls._assemble_benchmark_metrics(
            backtest=backtest,
            equity_curve_data=equity_curve_data,
            current_user=current_user,
            db=db,
            requested_benchmark=benchmark_asset,
        )
        warnings.extend(bm_warn)

        # KPIs
        kpis = cls._assemble_kpis(summary_metrics, equity_curve_data)

        # Asset allocations
        allocations, alloc_warn = cls._assemble_allocations(backtest, current_user, db)
        warnings.extend(alloc_warn)
        # Top holdings for Fact Sheet (top 10 sorted by weight)
        top_holdings = sorted(allocations, key=lambda x: x.effective_weight, reverse=True)[:10]

        # Time series points (downsampled to compact summary if needed)
        time_series_points = cls._assemble_timeseries_points(equity_curve_data, bm_series)
        compact_wealth_curve = cls._downsample_timeseries(time_series_points, max_points=250)

        # Monthly returns grid
        monthly_returns = cls._assemble_monthly_returns(equity_curve_data, bm_series)

        envelope.warnings = warnings

        return StrategyFactSheetPayload(
            envelope=envelope,
            mandate=mandate,
            kpis=kpis,
            benchmark_metrics=benchmark_metrics,
            top_holdings=top_holdings,
            compact_wealth_curve=compact_wealth_curve,
            monthly_returns=monthly_returns,
        )

    @classmethod
    def assemble_tear_sheet(
        cls,
        backtest_id: str,
        current_user: UserModel,
        db: Session,
        benchmark_asset: str | None = None,
    ) -> InstitutionalTearSheetPayload:
        """
        Compiles the 2-Page Comprehensive Institutional Tear Sheet payload for an authorized backtest.
        """
        backtest = cls._get_authorized_backtest(backtest_id, current_user, db)
        envelope, warnings = cls._assemble_envelope(
            report_type="tear_sheet",
            backtest=backtest,
            current_user=current_user,
            db=db,
        )

        mandate = cls._assemble_mandate(backtest)
        equity_curve_data = backtest.get_equity_curve()
        summary_metrics = backtest.get_summary_metrics()

        # Benchmark metrics
        benchmark_metrics, bm_series, bm_warn = cls._assemble_benchmark_metrics(
            backtest=backtest,
            equity_curve_data=equity_curve_data,
            current_user=current_user,
            db=db,
            requested_benchmark=benchmark_asset,
        )
        warnings.extend(bm_warn)

        # KPIs
        kpis = cls._assemble_kpis(summary_metrics, equity_curve_data)

        # Full Asset allocations
        allocations, alloc_warn = cls._assemble_allocations(backtest, current_user, db)
        warnings.extend(alloc_warn)

        # Friction & TCA metrics
        friction = cls._assemble_friction_metrics(backtest, summary_metrics, len(equity_curve_data))
        if friction and friction.slippage_bps == 0.0:
            warnings.append(
                ReportWarning(
                    code="WARN_PARTIAL_TCA",
                    severity="info",
                    message="Trading transaction costs modeled without price slippage.",
                    affected_metric="friction_drag_bps",
                )
            )

        # Full synchronized daily equity series
        equity_curve = cls._assemble_timeseries_points(equity_curve_data, bm_series)

        # Monthly returns matrix
        monthly_returns_table = cls._assemble_monthly_returns(equity_curve_data, bm_series)

        envelope.warnings = warnings

        return InstitutionalTearSheetPayload(
            envelope=envelope,
            mandate=mandate,
            kpis=kpis,
            benchmark_metrics=benchmark_metrics,
            asset_allocation=allocations,
            friction_and_execution=friction,
            equity_curve=equity_curve,
            monthly_returns_table=monthly_returns_table,
        )

    @classmethod
    def assemble_research_annex(
        cls,
        experiment_id: str,
        current_user: UserModel,
        db: Session,
        req: OverfittingDiagnosticsRequest | None = None,
    ) -> ResearchDiagnosticsAnnexPayload:
        """
        Compiles the 3rd-Page Research Diagnostics Annex payload using Stage 33 diagnostics.
        """
        # Enforce experiment authorization
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != current_user.id and current_user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        # Prepare request payload for ResearchService
        if req is None:
            req = OverfittingDiagnosticsRequest(experiment_id=experiment_id)
        elif not req.experiment_id:
            req.experiment_id = experiment_id

        # Reuse validated Stage 33 numerical engine
        res = ResearchService.compute_experiment_overfitting(
            experiment_id=experiment_id,
            req=req,
            user=current_user,
            db=db,
        )

        warnings: list[ReportWarning] = []
        for w in res.warnings:
            warnings.append(
                ReportWarning(
                    code="WARN_RESEARCH_DIAGNOSTICS",
                    severity="warning" if "severe" in w.lower() else "info",
                    message=w,
                )
            )

        # Snapshot resolution
        snapshot_digest = None
        if res.snapshot_id:
            snap = db.get(DatasetSnapshotModel, res.snapshot_id)
            if snap:
                snapshot_digest = snap.manifest_sha256
        else:
            warnings.append(
                ReportWarning(
                    code="WARN_MUTABLE_DATASET",
                    severity="warning",
                    message="Research experiment executed without certified immutable dataset snapshot.",
                    provenance_ref=res.dataset_id,
                )
            )

        now_utc = datetime.now(timezone.utc)
        envelope = CommonReportEnvelope(
            contract_version="1.0",
            report_type="research_diagnostics",
            report_title=f"Research Diagnostics Annex — {res.experiment_name}",
            generated_at=now_utc,
            base_currency="USD",
            reporting_start_date=res.generated_at.strftime("%Y-%m-%d"),
            reporting_end_date=res.generated_at.strftime("%Y-%m-%d"),
            dataset_id=res.dataset_id,
            snapshot_id=res.snapshot_id,
            snapshot_manifest_digest=snapshot_digest,
            source_experiment_id=res.experiment_id,
            source_run_id=res.best_run_id,
            calculation_version="1.0",
            warnings=warnings,
            is_hypothetical=True,
        )

        return ResearchDiagnosticsAnnexPayload(
            envelope=envelope,
            evaluated_runs_count=res.evaluated_runs_count,
            aligned_observations_count=res.aligned_observations_count,
            n_slices=res.n_slices,
            total_combinations_count=res.total_combinations_count,
            pbo=res.pbo,
            pbo_risk_level=res.pbo_risk_level,
            best_run_id=res.best_run_id,
            best_run_number=res.best_run_number,
            best_nominal_sharpe=res.best_nominal_sharpe,
            expected_max_sharpe=res.expected_max_sharpe,
            deflated_sharpe_ratio=res.deflated_sharpe_ratio,
            is_statistically_significant=res.is_statistically_significant,
            min_backtest_length_years=res.min_backtest_length_years,
            actual_backtest_length_years=res.actual_backtest_length_years,
            skewness=res.skewness,
            kurtosis=res.kurtosis,
            degradation_regression=res.degradation_regression,
            combinations_sample=res.combinations_sample,
            rank_distribution=res.rank_distribution,
            runs_summary=res.runs_summary,
        )

    @classmethod
    def assemble_unified_report(
        cls,
        backtest_id: str,
        current_user: UserModel,
        db: Session,
        benchmark_asset: str | None = None,
        experiment_id: str | None = None,
    ) -> InstitutionalReportResponse:
        """
        Compiles unified multi-report response bundling Fact Sheet, Tear Sheet,
        and optional Research Diagnostics Annex.
        """
        fact_sheet = cls.assemble_fact_sheet(
            backtest_id=backtest_id,
            current_user=current_user,
            db=db,
            benchmark_asset=benchmark_asset,
        )
        tear_sheet = cls.assemble_tear_sheet(
            backtest_id=backtest_id,
            current_user=current_user,
            db=db,
            benchmark_asset=benchmark_asset,
        )

        # Assemble Research Annex if experiment is explicitly specified or linked via run
        research_annex = None
        target_exp_id = experiment_id
        if not target_exp_id:
            # Check if this backtest is linked to any experiment run
            linked_run = (
                db.query(ResearchExperimentRunModel)
                .filter(ResearchExperimentRunModel.backtest_id == backtest_id)
                .first()
            )
            if linked_run:
                target_exp_id = linked_run.experiment_id

        if target_exp_id:
            try:
                research_annex = cls.assemble_research_annex(
                    experiment_id=target_exp_id,
                    current_user=current_user,
                    db=db,
                )
            except Exception as exc:
                logger.info("Research annex omitted from unified report: %s", exc)
                research_annex = None

        now_utc = datetime.now(timezone.utc)
        unified_envelope = CommonReportEnvelope(
            contract_version="1.0",
            report_type="unified_tear_sheet",
            report_title=f"Institutional Report Portfolio Suite — {fact_sheet.envelope.report_title}",
            generated_at=now_utc,
            base_currency=fact_sheet.envelope.base_currency,
            reporting_start_date=fact_sheet.envelope.reporting_start_date,
            reporting_end_date=fact_sheet.envelope.reporting_end_date,
            dataset_id=fact_sheet.envelope.dataset_id,
            dataset_filename=fact_sheet.envelope.dataset_filename,
            snapshot_id=fact_sheet.envelope.snapshot_id,
            snapshot_manifest_digest=fact_sheet.envelope.snapshot_manifest_digest,
            source_backtest_id=backtest_id,
            source_experiment_id=target_exp_id,
            calculation_version="1.0",
            warnings=fact_sheet.envelope.warnings,
            is_hypothetical=True,
        )

        return InstitutionalReportResponse(
            envelope=unified_envelope,
            fact_sheet=fact_sheet,
            tear_sheet=tear_sheet,
            research_annex=research_annex,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _get_authorized_backtest(
        cls,
        backtest_id: str,
        current_user: UserModel,
        db: Session,
    ) -> BacktestRunModel:
        """
        Retrieves a BacktestRunModel enforcing user ownership or admin privileges.
        Fails closed with HTTP 404 for nonexistent or unauthorized entities.
        """
        backtest = db.get(BacktestRunModel, backtest_id)
        if not backtest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run '{backtest_id}' not found.",
            )
        if backtest.user_id != current_user.id and current_user.role != "admin":
            # Prevent ID enumeration
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run '{backtest_id}' not found.",
            )
        return backtest

    @classmethod
    def _assemble_envelope(
        cls,
        report_type: str,
        backtest: BacktestRunModel,
        current_user: UserModel,
        db: Session,
    ) -> tuple[CommonReportEnvelope, list[ReportWarning]]:
        """
        Constructs the CommonReportEnvelope with data lineage, snapshot verification,
        and sanitization of date ordering.
        """
        warnings: list[ReportWarning] = []
        summary = backtest.get_summary_metrics()

        # Date handling & OBS-34-A-01 sanitization
        start_date_str = summary.get("effective_start_date") or (
            backtest.start_date.isoformat() if backtest.start_date else None
        )
        end_date_str = summary.get("effective_end_date") or (
            backtest.end_date.isoformat() if backtest.end_date else None
        )

        if not start_date_str or not end_date_str:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date_str = start_date_str or now_str
            end_date_str = end_date_str or now_str

        # Validate with date.fromisoformat
        try:
            d_start = date.fromisoformat(start_date_str)
            d_end = date.fromisoformat(end_date_str)
            if d_start > d_end:
                # Swap or fail
                d_start, d_end = d_end, d_start
                start_date_str, end_date_str = d_start.isoformat(), d_end.isoformat()
                warnings.append(
                    ReportWarning(
                        code="WARN_DATE_REORDERED",
                        severity="warning",
                        message="Source record had start date after end date; inverted for valid chronological ordering.",
                    )
                )
            
            # Check calendar duration
            days_span = (d_end - d_start).days
            if days_span < 180:
                warnings.append(
                    ReportWarning(
                        code="WARN_INCOMPLETE_CALENDAR_YEAR",
                        severity="info",
                        message=f"Reporting track record covers partial period ({days_span} calendar days). Annualized figures are scaled.",
                        affected_metric="cagr_net",
                    )
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid date representation in backtest record: {exc}",
            )

        # Snapshot lineage
        snapshot_id = backtest.snapshot_id
        snapshot_digest = None
        if snapshot_id:
            snap = db.get(DatasetSnapshotModel, snapshot_id)
            if snap:
                snapshot_digest = snap.manifest_sha256
        else:
            warnings.append(
                ReportWarning(
                    code="WARN_MUTABLE_DATASET",
                    severity="warning",
                    message="Report compiled from uncertified operational dataset without immutable snapshot manifest.",
                    provenance_ref=backtest.dataset_id,
                )
            )

        # Dataset details
        dataset_filename = None
        base_currency = "USD"
        dataset = db.get(DatasetModel, backtest.dataset_id)
        if dataset:
            dataset_filename = dataset.filename
            # Inspect currency of assets if available
            currencies = {a.currency for a in dataset.assets if a.currency}
            if len(currencies) == 1:
                base_currency = next(iter(currencies))
            elif len(currencies) > 1:
                base_currency = "USD"
                warnings.append(
                    ReportWarning(
                        code="WARN_MIXED_CURRENCIES",
                        severity="warning",
                        message=f"Dataset contains constituent assets in multiple currencies ({sorted(currencies)}).",
                        provenance_ref=dataset.id,
                    )
                )

        # Linked experiment run discovery
        source_exp_id = None
        source_run_id = None
        linked_run = (
            db.query(ResearchExperimentRunModel)
            .filter(ResearchExperimentRunModel.backtest_id == backtest.id)
            .first()
        )
        if linked_run:
            source_exp_id = linked_run.experiment_id
            source_run_id = linked_run.id

        envelope = CommonReportEnvelope(
            contract_version="1.0",
            report_type=report_type,  # type: ignore
            report_title=backtest.name or "Institutional Strategy Performance Report",
            generated_at=datetime.now(timezone.utc),
            base_currency=base_currency,
            reporting_start_date=start_date_str,
            reporting_end_date=end_date_str,
            dataset_id=backtest.dataset_id,
            dataset_filename=dataset_filename,
            snapshot_id=snapshot_id,
            snapshot_manifest_digest=snapshot_digest,
            source_backtest_id=backtest.id,
            source_experiment_id=source_exp_id,
            source_run_id=source_run_id,
            calculation_version="1.0",
            warnings=warnings,
            is_hypothetical=True,
        )

        return envelope, warnings

    @classmethod
    def _assemble_mandate(cls, backtest: BacktestRunModel) -> StrategyMandate:
        """
        Extracts operational mandate, universe, constraints, and rebalancing frequency.
        """
        strat_cfg = backtest.get_strategy_config()
        universe: list[str] = []
        if "assets" in strat_cfg and isinstance(strat_cfg["assets"], list):
            universe = [str(a) for a in strat_cfg["assets"]]
        elif "weights" in strat_cfg and isinstance(strat_cfg["weights"], dict):
            universe = list(strat_cfg["weights"].keys())

        constraints_summary: list[str] = []
        if strat_cfg.get("use_point_in_time"):
            constraints_summary.append("Strict Point-in-Time Corporate Actions")
        if backtest.strategy_type == "target_weights":
            constraints_summary.append("Target Weight Rebalancing")
        elif backtest.strategy_type == "equal_weight":
            constraints_summary.append("Equal Weight Universe Allocation")
        elif backtest.strategy_type == "walk_forward_optimization":
            constraints_summary.append("Rolling Walk-Forward Mean-Variance Optimization")

        return StrategyMandate(
            strategy_type=backtest.strategy_type,
            investment_universe=universe,
            rebalance_frequency=backtest.rebalance_frequency,
            optimization_objective=strat_cfg.get("optimization_objective"),
            initial_capital=float(backtest.initial_capital),
            risk_free_rate=float(strat_cfg.get("risk_free_rate", 0.0)),
            constraints_summary=constraints_summary,
        )

    @classmethod
    def _assemble_kpis(
        cls,
        summary: dict[str, Any],
        equity_curve: list[dict[str, Any]],
    ) -> ExecutiveKPIs:
        """
        Assembles ExecutiveKPIs maintaining strict gross vs net separation,
        accurate win/loss statistics, and mathematical undefined semantics.
        """
        cum_ret_net = float(summary.get("cumulative_return_net", 0.0))
        cum_ret_gross = (
            float(summary["cumulative_return_gross"])
            if summary.get("cumulative_return_gross") is not None
            else None
        )
        cagr_net = float(summary.get("cagr_net", 0.0))
        cagr_gross = (
            float(summary["cagr_gross"])
            if summary.get("cagr_gross") is not None
            else None
        )
        ann_ret_net = float(summary.get("annualized_return_net", 0.0))
        ann_ret_gross = (
            float(summary["annualized_return_gross"])
            if summary.get("annualized_return_gross") is not None
            else None
        )
        vol_net = float(summary.get("volatility_annualized_net", 0.0))
        vol_gross = (
            float(summary["volatility_annualized_gross"])
            if summary.get("volatility_annualized_gross") is not None
            else None
        )

        # Sharpe & Sortino (None if volatility is zero or sample < 2)
        sr_net = float(summary["sharpe_ratio_net"]) if summary.get("sharpe_ratio_net") is not None else None
        sr_gross = float(summary["sharpe_ratio_gross"]) if summary.get("sharpe_ratio_gross") is not None else None
        sortino_net = float(summary["sortino_ratio_net"]) if summary.get("sortino_ratio_net") is not None else None
        sortino_gross = float(summary["sortino_ratio_gross"]) if summary.get("sortino_ratio_gross") is not None else None

        # Max Drawdown
        mdd_net = float(summary.get("max_drawdown_net", 0.0))
        mdd_gross = float(summary["max_drawdown_gross"]) if summary.get("max_drawdown_gross") is not None else None

        # Calmar Ratio: CAGR / MaxDrawdown (None if max drawdown <= 1e-6)
        calmar_net = (cagr_net / mdd_net) if mdd_net > 1e-6 else None
        calmar_gross = None
        if cagr_gross is not None and mdd_gross is not None and mdd_gross > 1e-6:
            calmar_gross = cagr_gross / mdd_gross

        # Drawdown recovery and win/loss analysis from equity curve
        peak_date = summary.get("drawdown_peak_date")
        trough_date = summary.get("drawdown_trough_date")
        recovery_date = None
        duration_days = None

        pos_count = 0
        neg_count = 0
        gains: list[float] = []
        losses: list[float] = []

        if equity_curve:
            # Win/Loss rates
            for pt in equity_curve:
                r = float(pt.get("return_net", 0.0))
                if r > 0.0:
                    pos_count += 1
                    gains.append(r)
                elif r < 0.0:
                    neg_count += 1
                    losses.append(abs(r))

            # Recovery date tracking
            if peak_date and trough_date:
                # Find peak wealth
                peak_val = None
                past_trough = False
                for pt in equity_curve:
                    d = str(pt.get("date", ""))
                    v = float(pt.get("portfolio_value_net", 0.0))
                    if d == peak_date:
                        peak_val = v
                    if d == trough_date:
                        past_trough = True
                    if past_trough and peak_val is not None and v >= peak_val:
                        recovery_date = d
                        try:
                            duration_days = (date.fromisoformat(recovery_date) - date.fromisoformat(peak_date)).days
                        except Exception:
                            duration_days = None
                        break

                if duration_days is None and peak_date and trough_date:
                    try:
                        duration_days = (date.fromisoformat(trough_date) - date.fromisoformat(peak_date)).days
                    except Exception:
                        duration_days = None

        total_active_periods = pos_count + neg_count
        win_rate = (pos_count / total_active_periods) if total_active_periods > 0 else None
        avg_gain = float(np.mean(gains)) if gains else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        profit_loss_ratio = (avg_gain / avg_loss) if avg_loss > 1e-12 else None

        obs_count = int(summary.get("observation_count") or len(equity_curve) or 1)
        periods_year = int(summary.get("periods_per_year") or 252)

        return ExecutiveKPIs(
            cumulative_return_net=cum_ret_net,
            cumulative_return_gross=cum_ret_gross,
            cagr_net=cagr_net,
            cagr_gross=cagr_gross,
            annualized_return_net=ann_ret_net,
            annualized_return_gross=ann_ret_gross,
            annualized_volatility_net=vol_net,
            annualized_volatility_gross=vol_gross,
            sharpe_ratio_net=sr_net,
            sharpe_ratio_gross=sr_gross,
            sortino_ratio_net=sortino_net,
            sortino_ratio_gross=sortino_gross,
            max_drawdown_net=mdd_net,
            max_drawdown_gross=mdd_gross,
            calmar_ratio_net=calmar_net,
            calmar_ratio_gross=calmar_gross,
            drawdown_peak_date=peak_date,
            drawdown_trough_date=trough_date,
            drawdown_recovery_date=recovery_date,
            drawdown_duration_days=duration_days,
            positive_periods_count=pos_count,
            negative_periods_count=neg_count,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            observation_count=obs_count,
            periods_per_year=periods_year,
        )

    @classmethod
    def _assemble_benchmark_metrics(
        cls,
        backtest: BacktestRunModel,
        equity_curve_data: list[dict[str, Any]],
        current_user: UserModel,
        db: Session,
        requested_benchmark: str | None = None,
    ) -> tuple[BenchmarkRelativeMetrics | None, pd.Series | None, list[ReportWarning]]:
        """
        Resolves or computes benchmark attribution analytics against actual price observations.
        Returns (BenchmarkRelativeMetrics, aligned_benchmark_series, warnings).
        """
        warnings: list[ReportWarning] = []
        if not equity_curve_data:
            return None, None, warnings

        # 1. Check if a linked PerformanceReportModel already exists
        target_benchmark = requested_benchmark
        linked_report = None
        if not target_benchmark:
            linked_report = (
                db.query(PerformanceReportModel)
                .filter(PerformanceReportModel.backtest_id == backtest.id)
                .first()
            )
            if linked_report:
                target_benchmark = linked_report.benchmark_asset

        if not target_benchmark:
            warnings.append(
                ReportWarning(
                    code="WARN_NO_BENCHMARK",
                    severity="info",
                    message="No benchmark asset specified or linked; active comparative return metrics omitted.",
                )
            )
            return None, None, warnings

        # 2. Extract benchmark return series from dataset rows
        dataset_rows = get_dataset_rows(backtest.dataset_id)
        if not dataset_rows:
            warnings.append(
                ReportWarning(
                    code="WARN_DATASET_BARS_EMPTY",
                    severity="warning",
                    message=f"Dataset '{backtest.dataset_id}' contains no price bars for benchmark alignment.",
                )
            )
            return None, None, warnings

        try:
            bench_price_series = _extract_single_asset_series(dataset_rows, target_benchmark)
        except Exception:
            warnings.append(
                ReportWarning(
                    code="WARN_BENCHMARK_NOT_FOUND",
                    severity="warning",
                    message=f"Benchmark asset '{target_benchmark}' was not found in dataset.",
                    provenance_ref=target_benchmark,
                )
            )
            return None, None, warnings

        # Calculate portfolio returns series from net equity curve
        df_eq = pd.DataFrame(equity_curve_data).drop_duplicates(subset=["date"]).sort_values("date")
        p_series = pd.Series(df_eq["return_net"].values, index=df_eq["date"].values, dtype=float)
        b_series = bench_price_series.pct_change().dropna()

        try:
            p_aligned, b_aligned = align_return_series(p_series, b_series)
        except Exception as exc:
            warnings.append(
                ReportWarning(
                    code="WARN_BENCHMARK_ALIGNMENT_FAILED",
                    severity="warning",
                    message=f"Failed to synchronize benchmark '{target_benchmark}' with portfolio: {exc}",
                )
            )
            return None, None, warnings

        # Comparative evaluation
        comp = evaluate_comparative_performance(
            p_aligned,
            b_aligned,
            risk_free_rate_annual=0.0,
            periods_per_year=252,
        )

        # Correlation
        corr = float(p_aligned.corr(b_aligned)) if len(p_aligned) >= 3 else None

        bm_metrics = BenchmarkRelativeMetrics(
            benchmark_id=target_benchmark,
            benchmark_name=f"{target_benchmark} Benchmark Index",
            benchmark_cumulative_return=comp.benchmark_cumulative_return,
            benchmark_annualized_return=comp.benchmark_annualized_return,
            benchmark_annualized_volatility=comp.benchmark_annualized_volatility,
            benchmark_sharpe_ratio=comp.benchmark_sharpe_ratio,
            benchmark_max_drawdown=comp.benchmark_max_drawdown,
            arithmetic_active_return=comp.arithmetic_active_return,
            geometric_excess_return=comp.geometric_excess_return,
            annualized_active_return=comp.annualized_active_return,
            tracking_error=comp.tracking_error,
            information_ratio=comp.information_ratio,
            beta=comp.beta,
            alpha_annualized=comp.alpha_annualized,
            treynor_ratio=comp.treynor_ratio,
            up_capture_ratio=comp.up_capture_ratio,
            down_capture_ratio=comp.down_capture_ratio,
            correlation=corr,
        )

        return bm_metrics, b_aligned, warnings

    @classmethod
    def _assemble_allocations(
        cls,
        backtest: BacktestRunModel,
        current_user: UserModel,
        db: Session,
    ) -> tuple[list[AssetAllocationItem], list[ReportWarning]]:
        """
        Resolves asset-level holdings and Menchero contributions.
        """
        warnings: list[ReportWarning] = []
        strat_cfg = backtest.get_strategy_config()

        weights_map: dict[str, float] = {}
        if "weights" in strat_cfg and isinstance(strat_cfg["weights"], dict):
            weights_map = {str(k): float(v) for k, v in strat_cfg["weights"].items()}

        # Next check empirical effective_weights from summary_metrics
        if not weights_map:
            summary = backtest.get_summary_metrics()
            ew = summary.get("effective_weights")
            if isinstance(ew, dict):
                weights_map = {str(k): float(v) for k, v in ew.items()}
            elif isinstance(ew, list):
                for item in ew:
                    if isinstance(item, dict) and "asset" in item and "weight" in item:
                        weights_map[str(item["asset"])] = float(item["weight"])

        # Fallback to equal weighting if only an unweighted list of symbols is provided
        if not weights_map:
            if "assets" in strat_cfg and isinstance(strat_cfg["assets"], list):
                n = len(strat_cfg["assets"])
                weights_map = {str(a): 1.0 / n for a in strat_cfg["assets"]} if n > 0 else {}
            elif "universe" in strat_cfg and isinstance(strat_cfg["universe"], list):
                n = len(strat_cfg["universe"])
                weights_map = {str(a): 1.0 / n for a in strat_cfg["universe"]} if n > 0 else {}

        # Check if linked performance report has contributions
        linked_report = (
            db.query(PerformanceReportModel)
            .filter(PerformanceReportModel.backtest_id == backtest.id)
            .first()
        )
        contributions_map: dict[str, dict[str, float]] = {}
        if linked_report:
            for item in linked_report.get_contributions():
                asset = item.get("asset")
                if asset:
                    contributions_map[asset] = {
                        "cumulative_return": float(item.get("cumulative_return", 0.0)),
                        "total_contribution": float(item.get("total_contribution", 0.0)),
                        "share_of_return": float(item.get("share_of_return", 0.0)),
                    }

        if not weights_map:
            warnings.append(
                ReportWarning(
                    code="WARN_MISSING_ALLOCATION",
                    severity="info",
                    message="Portfolio contains no constituent weight allocations (cash-only or benchmark tracker).",
                )
            )
            return [], warnings

        allocations: list[AssetAllocationItem] = []
        for ticker, weight in weights_map.items():
            market = "US"
            asset_id = ticker
            if ":" in ticker:
                parts = ticker.split(":")
                ticker_clean = parts[0]
                market = parts[1]
                asset_id = ticker
            else:
                ticker_clean = ticker
                asset_id = f"{ticker}:US"

            contrib = contributions_map.get(ticker) or contributions_map.get(asset_id)
            cum_ret = contrib["cumulative_return"] if contrib else None
            tot_contrib = contrib["total_contribution"] if contrib else None
            share_ret = contrib["share_of_return"] if contrib else None

            allocations.append(
                AssetAllocationItem(
                    asset_id=asset_id,
                    ticker=ticker_clean,
                    market=market,
                    name=f"{ticker_clean} ({market})",
                    target_weight=float(weight),
                    effective_weight=float(weight),
                    asset_cumulative_return=cum_ret,
                    total_contribution=tot_contrib,
                    share_of_return=share_ret,
                )
            )

        return allocations, warnings

    @classmethod
    def _assemble_friction_metrics(
        cls,
        backtest: BacktestRunModel,
        summary: dict[str, Any],
        n_obs: int,
    ) -> FrictionAndExecutionMetrics:
        """
        Constructs FrictionAndExecutionMetrics from summary and backtest parameters.
        """
        turnover = float(summary.get("total_turnover", 0.0))
        ann_turnover = (turnover * 252.0 / n_obs) if n_obs > 0 else None
        t_cost_bps = float(backtest.transaction_cost_bps)
        slip_bps = float(backtest.slippage_bps)
        total_tc = float(summary.get("total_transaction_costs", 0.0))
        total_sc = float(summary.get("total_slippage_costs", 0.0))
        total_fc = float(summary.get("total_friction_costs", 0.0))

        drag_bps = 0.0
        init_cap = float(backtest.initial_capital)
        if init_cap > 0:
            drag_bps = (total_fc / init_cap) * 10000.0

        n_reb = int(summary.get("number_of_rebalances", 0))

        return FrictionAndExecutionMetrics(
            total_turnover=turnover,
            annualized_turnover=ann_turnover,
            transaction_cost_bps=t_cost_bps,
            slippage_bps=slip_bps,
            total_transaction_costs=total_tc,
            total_slippage_costs=total_sc,
            total_friction_costs=total_fc,
            friction_drag_bps=drag_bps,
            number_of_rebalances=n_reb,
        )

    @classmethod
    def _assemble_timeseries_points(
        cls,
        equity_curve_data: list[dict[str, Any]],
        bm_series: pd.Series | None,
    ) -> list[TimeSeriesPoint]:
        """
        Builds synchronized daily time series with normalized portfolio and benchmark wealth.
        """
        if not equity_curve_data:
            return []

        bm_map: dict[str, float] = {}
        bm_cum_map: dict[str, float] = {}
        bm_dd_map: dict[str, float] = {}

        if bm_series is not None and not bm_series.empty:
            bm_cum = np.cumprod(1.0 + bm_series)
            bm_dd = drawdown_series(bm_series)
            for idx, dt in enumerate(bm_series.index):
                dt_str = str(dt)
                bm_map[dt_str] = float(bm_series.iloc[idx])
                bm_cum_map[dt_str] = float(bm_cum.iloc[idx])
                bm_dd_map[dt_str] = float(bm_dd.iloc[idx])

        points: list[TimeSeriesPoint] = []
        base_nav = float(equity_curve_data[0].get("portfolio_value_net", 100000.0))

        for pt in equity_curve_data:
            dt = str(pt.get("date", ""))
            v_net = float(pt.get("portfolio_value_net", 0.0))
            v_gross = float(pt["portfolio_value_gross"]) if pt.get("portfolio_value_gross") is not None else None
            r_net = float(pt.get("return_net", 0.0))
            r_gross = float(pt["return_gross"]) if pt.get("return_gross") is not None else None
            dd_net = float(pt.get("drawdown_net", 0.0))
            dd_gross = float(pt["drawdown_gross"]) if pt.get("drawdown_gross") is not None else None

            bm_val = (bm_cum_map[dt] * base_nav) if dt in bm_cum_map else None
            bm_ret = bm_map.get(dt)
            bm_dd = bm_dd_map.get(dt)

            points.append(
                TimeSeriesPoint(
                    date=dt,
                    portfolio_value_net=v_net,
                    portfolio_value_gross=v_gross,
                    return_net=r_net,
                    return_gross=r_gross,
                    drawdown_net=dd_net,
                    drawdown_gross=dd_gross,
                    benchmark_value=bm_val,
                    benchmark_return=bm_ret,
                    benchmark_drawdown=bm_dd,
                )
            )

        return points

    @classmethod
    def _downsample_timeseries(
        cls,
        points: list[TimeSeriesPoint],
        max_points: int = 250,
    ) -> list[TimeSeriesPoint]:
        """
        Downsamples high-frequency daily series for compact 1-page charts.
        Always preserves the first and last points.
        """
        n = len(points)
        if n <= max_points:
            return points

        # Use evenly spaced indices ensuring total count <= max_points and preserving endpoints
        indices = np.round(np.linspace(0, n - 1, max_points)).astype(int).tolist()
        unique_indices = list(dict.fromkeys(indices))
        return [points[i] for i in unique_indices]

    @classmethod
    def _assemble_monthly_returns(
        cls,
        equity_curve_data: list[dict[str, Any]],
        bm_series: pd.Series | None,
    ) -> list[MonthlyReturnCell]:
        """
        Computes discrete compounded monthly returns: R_M = prod(1 + r_t) - 1.
        """
        if not equity_curve_data:
            return []

        # Group by (year, month)
        monthly_net: dict[tuple[int, int], list[float]] = defaultdict(list)
        monthly_gross: dict[tuple[int, int], list[float]] = defaultdict(list)

        for pt in equity_curve_data:
            d_str = str(pt.get("date", ""))
            try:
                d = date.fromisoformat(d_str)
                key = (d.year, d.month)
                r_net = float(pt.get("return_net", 0.0))
                monthly_net[key].append(r_net)
                if pt.get("return_gross") is not None:
                    monthly_gross[key].append(float(pt["return_gross"]))
            except Exception:
                continue

        monthly_bm: dict[tuple[int, int], list[float]] = defaultdict(list)
        if bm_series is not None:
            for dt, val in bm_series.items():
                try:
                    d = date.fromisoformat(str(dt))
                    monthly_bm[(d.year, d.month)].append(float(val))
                except Exception:
                    continue

        cells: list[MonthlyReturnCell] = []
        for key in sorted(monthly_net.keys()):
            yr, mo = key
            ret_net = float(np.prod([1.0 + r for r in monthly_net[key]]) - 1.0)
            ret_gross = None
            if key in monthly_gross and monthly_gross[key]:
                ret_gross = float(np.prod([1.0 + r for r in monthly_gross[key]]) - 1.0)

            ret_bm = None
            if key in monthly_bm and monthly_bm[key]:
                ret_bm = float(np.prod([1.0 + r for r in monthly_bm[key]]) - 1.0)

            cells.append(
                MonthlyReturnCell(
                    year=yr,
                    month=mo,
                    return_net=ret_net,
                    return_gross=ret_gross,
                    benchmark_return=ret_bm,
                )
            )

        return cells
