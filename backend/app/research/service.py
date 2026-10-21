"""
Service layer for portfolio research experiments, reproducible run execution,
provenance verification, and multi-run strategy comparison.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.analytics.overfitting import compute_overfitting_diagnostics
from app.auth.dependencies import check_dataset_access
from app.backtesting.models import BacktestRequest
from app.backtesting.service import execute_backtest
from app.db.models import (
    BacktestRunModel,
    DatasetModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.performance.models import PerformanceAnalysisRequest
from app.performance.service import execute_performance_analysis
from app.research.fingerprint import canonical_json_dumps, compute_config_fingerprint
from app.research.overfitting_models import (
    OverfittingDiagnosticsRequest,
    OverfittingDiagnosticsResponse,
)
from app.research.models import (
    ComparisonRequest,
    ComparisonResponse,
    ComparisonRunMetricItem,
    ExperimentConfig,
    ExperimentCreateRequest,
    ExperimentListItem,
    ExperimentResponse,
    ExperimentRunListItem,
    ExperimentRunResponse,
    ExperimentUpdateRequest,
)
from app.risk_simulation.models import (
    DistributionModel,
    RebalancePolicy,
    RiskSimulationRequest,
)
from app.risk_simulation.service import execute_risk_simulation

logger = logging.getLogger(__name__)


class ResearchService:
    @staticmethod
    def create_experiment(
        req: ExperimentCreateRequest,
        user: UserModel,
        db: Session,
    ) -> ExperimentResponse:
        """
        Validates configuration and creates a persistent research experiment definition.
        """
        # 1. Enforce dataset ownership / tenant access
        dataset = check_dataset_access(db, req.dataset_id, user)

        # 2. Validate configuration schema and strategy parameters
        cfg_payload = dict(req.config)
        cfg_payload["strategy_type"] = req.strategy_type
        cfg_payload["dataset_id"] = req.dataset_id

        try:
            validated_config = ExperimentConfig(**cfg_payload)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Configuration validation failed: {exc}",
            )

        config_dict = validated_config.model_dump(mode="json")
        fingerprint = compute_config_fingerprint(config_dict)

        # 3. Create persistent record
        experiment = ResearchExperimentModel(
            id=str(uuid4()),
            user_id=user.id,
            dataset_id=dataset.id,
            name=req.name.strip(),
            description=req.description.strip() if req.description else None,
            strategy_type=req.strategy_type,
            config_json=canonical_json_dumps(config_dict),
            config_fingerprint=fingerprint,
            version=1,
        )

        db.add(experiment)
        db.commit()
        db.refresh(experiment)

        return ExperimentResponse(
            id=experiment.id,
            user_id=experiment.user_id,
            dataset_id=experiment.dataset_id,
            name=experiment.name,
            description=experiment.description,
            strategy_type=experiment.strategy_type,
            config=experiment.get_config(),
            config_fingerprint=experiment.config_fingerprint,
            version=experiment.version,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            latest_run_status=None,
            latest_run_number=None,
            total_runs_count=0,
        )

    @staticmethod
    def list_experiments(
        user: UserModel,
        db: Session,
    ) -> list[ExperimentListItem]:
        """
        Lists all research experiments owned by the authenticated user (or all if admin).
        """
        stmt = select(ResearchExperimentModel)
        if user.role != "admin":
            stmt = stmt.where(ResearchExperimentModel.user_id == user.id)
        stmt = stmt.order_by(desc(ResearchExperimentModel.created_at))

        experiments = db.scalars(stmt).all()
        results: list[ExperimentListItem] = []

        for exp in experiments:
            runs = exp.runs
            latest_run = runs[-1] if runs else None
            results.append(
                ExperimentListItem(
                    id=exp.id,
                    name=exp.name,
                    description=exp.description,
                    strategy_type=exp.strategy_type,
                    dataset_id=exp.dataset_id,
                    version=exp.version,
                    config_fingerprint=exp.config_fingerprint,
                    latest_run_status=latest_run.status if latest_run else None,
                    latest_run_number=latest_run.run_number if latest_run else None,
                    total_runs_count=len(runs),
                    created_at=exp.created_at,
                    updated_at=exp.updated_at,
                )
            )

        return results

    @staticmethod
    def get_experiment(
        experiment_id: str,
        user: UserModel,
        db: Session,
    ) -> ExperimentResponse:
        """
        Retrieves a single owned experiment by ID.
        """
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        runs = exp.runs
        latest_run = runs[-1] if runs else None

        return ExperimentResponse(
            id=exp.id,
            user_id=exp.user_id,
            dataset_id=exp.dataset_id,
            name=exp.name,
            description=exp.description,
            strategy_type=exp.strategy_type,
            config=exp.get_config(),
            config_fingerprint=exp.config_fingerprint,
            version=exp.version,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            latest_run_status=latest_run.status if latest_run else None,
            latest_run_number=latest_run.run_number if latest_run else None,
            total_runs_count=len(runs),
        )

    @staticmethod
    def update_experiment(
        experiment_id: str,
        req: ExperimentUpdateRequest,
        user: UserModel,
        db: Session,
    ) -> ExperimentResponse:
        """
        Updates an experiment. If semantic configuration fields are altered, increments the version.
        """
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        if req.name is not None:
            exp.name = req.name.strip()
        if req.description is not None:
            exp.description = req.description.strip()

        if req.config is not None:
            cfg_payload = dict(req.config)
            cfg_payload["strategy_type"] = cfg_payload.get("strategy_type", exp.strategy_type)
            cfg_payload["dataset_id"] = cfg_payload.get("dataset_id", exp.dataset_id)

            try:
                validated_config = ExperimentConfig(**cfg_payload)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Configuration validation failed: {exc}",
                )

            config_dict = validated_config.model_dump(mode="json")
            new_fingerprint = compute_config_fingerprint(config_dict)

            if new_fingerprint != exp.config_fingerprint:
                exp.version += 1
                exp.config_fingerprint = new_fingerprint
                exp.strategy_type = validated_config.strategy_type
                exp.dataset_id = validated_config.dataset_id

            exp.config_json = canonical_json_dumps(config_dict)

        exp.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exp)

        runs = exp.runs
        latest_run = runs[-1] if runs else None

        return ExperimentResponse(
            id=exp.id,
            user_id=exp.user_id,
            dataset_id=exp.dataset_id,
            name=exp.name,
            description=exp.description,
            strategy_type=exp.strategy_type,
            config=exp.get_config(),
            config_fingerprint=exp.config_fingerprint,
            version=exp.version,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            latest_run_status=latest_run.status if latest_run else None,
            latest_run_number=latest_run.run_number if latest_run else None,
            total_runs_count=len(runs),
        )

    @staticmethod
    def delete_experiment(
        experiment_id: str,
        user: UserModel,
        db: Session,
    ) -> None:
        """
        Deletes an owned experiment and cascades to its execution runs.
        """
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        db.delete(exp)
        db.commit()

    @staticmethod
    def execute_experiment_run(
        experiment_id: str,
        user: UserModel,
        db: Session,
    ) -> ExperimentRunResponse:
        """
        Executes a research experiment run via existing application services,
        persisting execution metadata, provenance, and summary KPIs.
        Reruns are strictly non-destructive (incrementing run_number).
        """
        # 1. Fetch experiment and verify ownership
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        # 2. Verify dataset access and capture immutable content hash
        dataset = check_dataset_access(db, exp.dataset_id, user)
        dataset_hash = dataset.content_sha256

        # 3. Determine next run number
        max_run = db.scalar(
            select(func.max(ResearchExperimentRunModel.run_number)).where(
                ResearchExperimentRunModel.experiment_id == exp.id
            )
        )
        run_number = (max_run or 0) + 1

        # 4. Initialize run record in 'running' state
        run_record = ResearchExperimentRunModel(
            id=str(uuid4()),
            experiment_id=exp.id,
            user_id=user.id,
            run_number=run_number,
            status="running",
            dataset_version_hash=dataset_hash,
            config_fingerprint=exp.config_fingerprint,
        )
        db.add(run_record)
        db.commit()
        db.refresh(run_record)

        config = exp.get_config()
        t0 = time.perf_counter()

        backtest_id: str | None = None
        performance_report_id: str | None = None
        risk_simulation_id: str | None = None
        summary_kpis: dict[str, Any] = {}
        error_msg: str | None = None

        dataset_currency = dataset.assets[0].currency if dataset.assets else "USD"

        try:
            # 5. Dispatch to existing analytical engine based on strategy_type
            if exp.strategy_type in ("target_weights", "equal_weight", "walk_forward_optimization"):
                bt_req = BacktestRequest(
                    dataset_id=exp.dataset_id,
                    name=f"{exp.name} (Run #{run_number})",
                    strategy_type=exp.strategy_type,
                    assets=config["assets"],
                    weights=config.get("weights"),
                    rebalance_frequency=config.get("rebalance_frequency") or "monthly",
                    initial_capital=float(config.get("initial_capital", 100000.0)),
                    transaction_cost_bps=float(config.get("transaction_cost_bps", 0.0)),
                    slippage_bps=float(config.get("slippage_bps", 0.0)),
                    start_date=config.get("start_date"),
                    end_date=config.get("end_date"),
                    training_window=int(config.get("training_window", 252)),
                    optimization_objective=config.get("objective") or "max_sharpe",
                    risk_free_rate=float(config.get("risk_free_rate", 0.0)),
                    snapshot_id=config.get("snapshot_id"),
                    auto_snapshot=bool(config.get("auto_snapshot", False)),
                )
                bt_resp = execute_backtest(bt_req, user, db)
                backtest_id = bt_resp.id
                if bt_resp.snapshot_id:
                    run_record.snapshot_id = bt_resp.snapshot_id
                elif config.get("snapshot_id"):
                    run_record.snapshot_id = config.get("snapshot_id")

                eq_curve = bt_resp.equity_curve
                summary_kpis = {
                    "currency": dataset_currency,
                    "cumulative_return": bt_resp.metrics.cumulative_return_net,
                    "cagr": bt_resp.metrics.cagr_net,
                    "annualized_volatility": bt_resp.metrics.volatility_annualized_net,
                    "sharpe_ratio": bt_resp.metrics.sharpe_ratio_net,
                    "sortino_ratio": bt_resp.metrics.sortino_ratio_net,
                    "max_drawdown": bt_resp.metrics.max_drawdown_net,
                    "turnover": bt_resp.metrics.total_turnover,
                    "total_friction_costs": bt_resp.metrics.total_friction_costs,
                    "final_value": bt_resp.metrics.final_value_net,
                    "start_date": eq_curve[0].date if eq_curve else None,
                    "end_date": eq_curve[-1].date if eq_curve else None,
                    "observations_count": len(eq_curve),
                    "active_return": None,
                    "tracking_error": None,
                    "information_ratio": None,
                    "var_95": None,
                    "cvar_95": None,
                }

            elif exp.strategy_type == "benchmark_attribution":
                perf_req = PerformanceAnalysisRequest(
                    dataset_id=exp.dataset_id,
                    name=f"{exp.name} (Run #{run_number})",
                    benchmark_asset=config["benchmark_asset"],
                    assets=config.get("assets"),
                    weights=config.get("weights"),
                    risk_free_rate=float(config.get("risk_free_rate", 0.0)),
                    start_date=config.get("start_date"),
                    end_date=config.get("end_date"),
                    save_report=True,
                )
                perf_resp = execute_performance_analysis(perf_req, user, db)
                performance_report_id = perf_resp.id

                summary_kpis = {
                    "currency": dataset_currency,
                    "cumulative_return": perf_resp.metrics.portfolio_cumulative_return,
                    "benchmark_cumulative_return": perf_resp.metrics.benchmark_cumulative_return,
                    "active_return": perf_resp.metrics.arithmetic_active_return,
                    "annualized_volatility": perf_resp.metrics.portfolio_annualized_volatility,
                    "sharpe_ratio": perf_resp.metrics.portfolio_sharpe_ratio,
                    "sortino_ratio": perf_resp.metrics.portfolio_sortino_ratio,
                    "max_drawdown": perf_resp.metrics.portfolio_max_drawdown,
                    "tracking_error": perf_resp.metrics.tracking_error,
                    "information_ratio": perf_resp.metrics.information_ratio,
                    "beta": perf_resp.metrics.beta,
                    "alpha": perf_resp.metrics.alpha_annualized,
                    "treynor_ratio": perf_resp.metrics.treynor_ratio,
                    "start_date": str(perf_resp.start_date) if perf_resp.start_date else None,
                    "end_date": str(perf_resp.end_date) if perf_resp.end_date else None,
                    "observations_count": perf_resp.metrics.observation_count,
                    "cagr": None,
                    "turnover": None,
                    "total_friction_costs": None,
                    "final_value": None,
                    "var_95": None,
                    "cvar_95": None,
                }

            elif exp.strategy_type == "monte_carlo_risk":
                dist_str = str(config.get("distribution", "normal")).lower()
                dist_enum = (
                    DistributionModel.MULTIVARIATE_STUDENT_T
                    if "student" in dist_str or "t" == dist_str
                    else DistributionModel.MULTIVARIATE_NORMAL
                )
                reb_str = str(config.get("rebalance_policy", "none")).lower()
                reb_enum = (
                    RebalancePolicy.CONSTANT_WEIGHTS
                    if "constant" in reb_str or "periodic" in reb_str
                    else RebalancePolicy.BUY_AND_HOLD
                )

                risk_req = RiskSimulationRequest(
                    dataset_id=exp.dataset_id,
                    name=f"{exp.name} (Run #{run_number})",
                    assets=config["assets"],
                    weights=config.get("weights") or {a: 1.0 / len(config["assets"]) for a in config["assets"]},
                    initial_capital=float(config.get("initial_capital", 100000.0)),
                    horizon_days=int(config.get("horizon_days", 21)),
                    num_paths=int(config.get("num_paths", 1000)),
                    distribution=dist_enum,
                    degrees_of_freedom=float(config.get("degrees_of_freedom", 5.0)),
                    rebalance_policy=reb_enum,
                    seed=config.get("seed"),
                )
                risk_resp = execute_risk_simulation(risk_req, user, db)
                risk_simulation_id = risk_resp.id

                var_95_val = None
                cvar_95_val = None
                for m in risk_resp.summary.var_cvar_metrics:
                    if abs(m.confidence_level - 0.95) < 0.005:
                        var_95_val = m.var_percentage
                        cvar_95_val = m.cvar_percentage

                summary_kpis = {
                    "currency": risk_resp.summary.currency,
                    "cumulative_return": risk_resp.summary.expected_terminal_return,
                    "expected_terminal_return": risk_resp.summary.expected_terminal_return,
                    "annualized_volatility": risk_resp.summary.terminal_return_volatility,
                    "var_95": var_95_val,
                    "cvar_95": cvar_95_val,
                    "prob_loss": risk_resp.summary.prob_negative_return,
                    "median_terminal_value": risk_resp.summary.median_terminal_value,
                    "final_value": risk_resp.summary.expected_terminal_value,
                    "initial_capital": risk_resp.summary.initial_capital,
                    "horizon_days": risk_req.horizon_days,
                    "num_paths": risk_req.num_paths,
                    "seed": risk_req.seed,
                    "distribution": risk_resp.distribution,
                    "cagr": None,
                    "sharpe_ratio": None,
                    "sortino_ratio": None,
                    "max_drawdown": None,
                    "active_return": None,
                    "tracking_error": None,
                    "information_ratio": None,
                    "turnover": None,
                    "total_friction_costs": None,
                    "start_date": None,
                    "end_date": None,
                    "observations_count": None,
                }
            else:
                raise ValueError(f"Unsupported experiment strategy archetype: {exp.strategy_type}")

            duration_ms = int((time.perf_counter() - t0) * 1000)
            run_record.status = "succeeded"
            run_record.execution_duration_ms = duration_ms
            run_record.backtest_id = backtest_id
            run_record.performance_report_id = performance_report_id
            run_record.risk_simulation_id = risk_simulation_id
            run_record.summary_kpis_json = json.dumps(summary_kpis)
            run_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run_record)

        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.exception("Experiment run #%d execution failed: %s", run_number, exc)
            run_record.status = "failed"
            run_record.execution_duration_ms = duration_ms
            run_record.error_message = str(exc)
            run_record.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run_record)

        reproducible, notes = ResearchService.check_run_reproducibility(run_record, db)

        return ExperimentRunResponse(
            id=run_record.id,
            experiment_id=run_record.experiment_id,
            run_number=run_record.run_number,
            status=run_record.status,
            dataset_version_hash=run_record.dataset_version_hash,
            snapshot_id=run_record.snapshot_id,
            config_fingerprint=run_record.config_fingerprint,
            execution_duration_ms=run_record.execution_duration_ms,
            backtest_id=run_record.backtest_id,
            performance_report_id=run_record.performance_report_id,
            risk_simulation_id=run_record.risk_simulation_id,
            summary_kpis=run_record.get_summary_kpis(),
            error_message=run_record.error_message,
            is_reproducible=reproducible,
            reproducibility_notes=notes,
            created_at=run_record.created_at,
            completed_at=run_record.completed_at,
        )

    @staticmethod
    def list_experiment_runs(
        experiment_id: str,
        user: UserModel,
        db: Session,
    ) -> list[ExperimentRunListItem]:
        """
        Lists all runs for a specific experiment in descending run_number order.
        """
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        runs = (
            db.query(ResearchExperimentRunModel)
            .filter(ResearchExperimentRunModel.experiment_id == experiment_id)
            .order_by(desc(ResearchExperimentRunModel.run_number))
            .all()
        )

        results: list[ExperimentRunListItem] = []
        for r in runs:
            reproducible, _ = ResearchService.check_run_reproducibility(r, db)
            results.append(
                ExperimentRunListItem(
                    id=r.id,
                    experiment_id=r.experiment_id,
                    run_number=r.run_number,
                    status=r.status,
                    snapshot_id=r.snapshot_id,
                    config_fingerprint=r.config_fingerprint,
                    execution_duration_ms=r.execution_duration_ms,
                    is_reproducible=reproducible,
                    created_at=r.created_at,
                    completed_at=r.completed_at,
                    summary_kpis=r.get_summary_kpis(),
                )
            )
        return results

    @staticmethod
    def get_experiment_run(
        run_id: str,
        user: UserModel,
        db: Session,
    ) -> ExperimentRunResponse:
        """
        Retrieves a single experiment run by ID with detailed reproducibility audit notes.
        """
        run_record = db.get(ResearchExperimentRunModel, run_id)
        if not run_record or (run_record.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment run '{run_id}' not found.",
            )

        reproducible, notes = ResearchService.check_run_reproducibility(run_record, db)

        return ExperimentRunResponse(
            id=run_record.id,
            experiment_id=run_record.experiment_id,
            run_number=run_record.run_number,
            status=run_record.status,
            dataset_version_hash=run_record.dataset_version_hash,
            snapshot_id=run_record.snapshot_id,
            config_fingerprint=run_record.config_fingerprint,
            execution_duration_ms=run_record.execution_duration_ms,
            backtest_id=run_record.backtest_id,
            performance_report_id=run_record.performance_report_id,
            risk_simulation_id=run_record.risk_simulation_id,
            summary_kpis=run_record.get_summary_kpis(),
            error_message=run_record.error_message,
            is_reproducible=reproducible,
            reproducibility_notes=notes,
            created_at=run_record.created_at,
            completed_at=run_record.completed_at,
        )

    @staticmethod
    def check_run_reproducibility(
        run: ResearchExperimentRunModel,
        db: Session,
    ) -> tuple[bool, list[str]]:
        """
        Evaluates whether a run can be faithfully reproduced from currently persisted assets.
        If bound to an immutable dataset snapshot, reproducibility is guaranteed against
        subsequent operational dataset mutations.
        """
        notes: list[str] = []
        if run.status != "succeeded":
            return False, [f"Run did not succeed (status: {run.status})."]

        exp = run.experiment
        if not exp:
            return False, ["Parent research experiment definition was removed."]

        # Check snapshot linkage first (Gate C frozen reproducibility)
        if run.snapshot_id:
            snap = run.snapshot
            if not snap:
                return False, [f"Referenced dataset snapshot '{run.snapshot_id}' could not be located."]
            if not snap.frozen_payload_json:
                return False, [f"Referenced dataset snapshot '{run.snapshot_id}' lacks frozen payload."]
            notes.append(
                f"Bound to immutable dataset snapshot '{run.snapshot_id}' "
                f"(digest={snap.manifest_sha256[:16]}..., status={snap.point_in_time_status})."
            )
            return True, notes

        dataset = db.get(DatasetModel, exp.dataset_id)
        if not dataset:
            return False, ["Referenced source dataset has been deleted."]

        if dataset.content_sha256 and run.dataset_version_hash:
            if dataset.content_sha256 != run.dataset_version_hash:
                return False, [
                    f"Dataset content has evolved since execution (run hash: {run.dataset_version_hash[:8]}..., current dataset hash: {dataset.content_sha256[:8]}...)."
                ]
            else:
                notes.append("Dataset content SHA-256 matches execution provenance.")
        else:
            notes.append("Dataset content hash unverified.")

        return True, notes

    @staticmethod
    def compare_experiment_runs(
        req: ComparisonRequest,
        user: UserModel,
        db: Session,
    ) -> ComparisonResponse:
        """
        Compares 2 to 10 completed experiment runs.
        Enforces currency homogeneity, identifies period and provenance divergence,
        and aggregates comparative metrics without fabricating data.
        """
        unique_run_ids = list(dict.fromkeys(req.run_ids))
        if len(unique_run_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Must provide at least 2 distinct run IDs to compare.",
            )

        runs = (
            db.query(ResearchExperimentRunModel)
            .filter(ResearchExperimentRunModel.id.in_(unique_run_ids))
            .all()
        )

        if len(runs) != len(unique_run_ids):
            found_ids = {r.id for r in runs}
            missing = [rid for rid in unique_run_ids if rid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run(s) not found: {missing}",
            )

        # Tenant isolation
        for r in runs:
            if r.user_id != user.id and user.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Research experiment run '{r.id}' not found.",
                )
            if r.status != "succeeded":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Run '{r.id}' (Run #{r.run_number}) did not succeed (status: {r.status}) and cannot be compared.",
                )

        # Currency validation
        currencies: list[str] = []
        for r in runs:
            kpis = r.get_summary_kpis()
            cur = kpis.get("currency") or "USD"
            currencies.append(cur)

        if len(set(currencies)) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Incompatible currencies across selected runs: {set(currencies)}. Cross-currency comparison is not supported without explicit FX rates.",
            )

        common_currency = currencies[0]

        # Check for period divergence
        dates = [
            (r.get_summary_kpis().get("start_date"), r.get_summary_kpis().get("end_date"))
            for r in runs
            if r.get_summary_kpis().get("start_date")
        ]
        has_period_divergence = len(set(dates)) > 1

        # Check for provenance divergence
        hashes = [r.dataset_version_hash for r in runs if r.dataset_version_hash]
        has_provenance_divergence = len(set(hashes)) > 1

        warnings: list[str] = []
        if has_period_divergence:
            warnings.append(
                "Evaluation periods diverge across selected runs. Metric comparisons should be interpreted with caution."
            )
        if has_provenance_divergence:
            warnings.append(
                "Selected runs were executed against different dataset versions. Underlying market data divergence may affect results."
            )

        # Build comparison items
        comparison_items: list[ComparisonRunMetricItem] = []
        for r in runs:
            exp = r.experiment
            kpis = r.get_summary_kpis()
            reproducible, _ = ResearchService.check_run_reproducibility(r, db)
            config = exp.get_config()

            config_summary = {
                "strategy_type": exp.strategy_type,
                "assets": config.get("assets", []),
                "rebalance_frequency": config.get("rebalance_frequency"),
                "transaction_cost_bps": config.get("transaction_cost_bps", 0.0),
                "slippage_bps": config.get("slippage_bps", 0.0),
                "objective": config.get("objective"),
                "benchmark_asset": config.get("benchmark_asset"),
                "risk_free_rate": config.get("risk_free_rate", 0.0),
                "seed": config.get("seed"),
            }

            comparison_items.append(
                ComparisonRunMetricItem(
                    run_id=r.id,
                    experiment_id=exp.id,
                    experiment_name=exp.name,
                    strategy_type=exp.strategy_type,
                    run_number=r.run_number,
                    status=r.status,
                    dataset_id=exp.dataset_id,
                    dataset_version_hash=r.dataset_version_hash,
                    config_fingerprint=r.config_fingerprint,
                    currency=common_currency,
                    is_reproducible=reproducible,
                    execution_date=r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    start_date=kpis.get("start_date"),
                    end_date=kpis.get("end_date"),
                    observations_count=kpis.get("observations_count"),
                    metrics=kpis,
                    config_summary=config_summary,
                )
            )

        return ComparisonResponse(
            runs=comparison_items,
            common_currency=common_currency,
            has_period_divergence=has_period_divergence,
            has_provenance_divergence=has_provenance_divergence,
            warnings=warnings,
        )

    @staticmethod
    def compute_experiment_overfitting(
        experiment_id: str,
        req: OverfittingDiagnosticsRequest,
        user: UserModel,
        db: Session,
    ) -> OverfittingDiagnosticsResponse:
        """
        Computes Combinatorially Symmetric Cross-Validation (CSCV), Probability of
        Backtest Overfitting (PBO), Deflated Sharpe Ratio (DSR), and Minimum Backtest
        Length (MinBTL) across completed strategy runs of a research experiment.

        Enforces tenant isolation, deterministic date alignment, run ordering,
        and fail-closed integrity validation.
        """
        # 1. Fetch experiment and enforce tenant authorization
        exp = db.get(ResearchExperimentModel, experiment_id)
        if not exp or (exp.user_id != user.id and user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research experiment '{experiment_id}' not found.",
            )

        # 2. Path / payload consistency check
        if req.experiment_id and req.experiment_id.strip() != experiment_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Experiment ID in request body '{req.experiment_id}' does not match URL path '{experiment_id}'.",
            )

        # 3. Select and validate eligible strategy runs
        if req.run_ids is not None:
            # Explicit run subset requested
            unique_req_ids = list(dict.fromkeys(req.run_ids))
            if len(unique_req_ids) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="At least 2 distinct run IDs are required for cross-validation.",
                )
            if len(unique_req_ids) > 100:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Maximum number of candidate strategies for on-demand overfitting analysis is 100.",
                )

            runs = (
                db.query(ResearchExperimentRunModel)
                .filter(ResearchExperimentRunModel.id.in_(unique_req_ids))
                .all()
            )

            found_ids = {r.id for r in runs}
            missing = [rid for rid in unique_req_ids if rid not in found_ids]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run(s) not found: {missing}",
                )

            # Validate each run belongs to this experiment and user
            for r in runs:
                if r.experiment_id != exp.id or (r.user_id != user.id and user.role != "admin"):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Research experiment run '{r.id}' not found.",
                    )
                if r.status != "succeeded":
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Run '{r.id}' (Run #{r.run_number}) did not succeed (status: {r.status}) and cannot be evaluated.",
                    )
                if not r.backtest_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Run '{r.id}' (Run #{r.run_number}) does not have an associated backtest simulation.",
                    )

            # Sort deterministically by run_number
            runs.sort(key=lambda r: r.run_number)
        else:
            # Query all succeeded runs for this experiment with an associated backtest
            runs = (
                db.query(ResearchExperimentRunModel)
                .filter(
                    ResearchExperimentRunModel.experiment_id == exp.id,
                    ResearchExperimentRunModel.status == "succeeded",
                    ResearchExperimentRunModel.backtest_id.isnot(None),
                )
                .order_by(ResearchExperimentRunModel.run_number)
                .all()
            )

        if len(runs) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"At least 2 eligible completed strategy runs with backtests are required for combinatorial cross-validation, found {len(runs)}.",
            )

        # 4. Extract equity curves and validate daily return series
        series_map: dict[str, pd.Series] = {}
        run_lengths: dict[str, int] = {}

        for r in runs:
            backtest = db.get(BacktestRunModel, r.backtest_id) if r.backtest_id else None
            if not backtest or not backtest.equity_curve_json:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Run '{r.id}' (Run #{r.run_number}) is missing equity curve data.",
                )

            curve = backtest.get_equity_curve()
            if not curve or len(curve) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Run '{r.id}' (Run #{r.run_number}) has insufficient equity curve observations ({len(curve) if curve else 0}).",
                )

            dates: list[str] = []
            returns: list[float] = []

            for pt in curve:
                d = pt.get("date")
                ret = pt.get("return_net")
                if not d or not isinstance(d, str):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Run '{r.id}' contains invalid observation date format.",
                    )
                if ret is None or not math.isfinite(ret):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Run '{r.id}' contains non-finite net return values.",
                    )
                dates.append(d)
                returns.append(float(ret))

            # Duplicate date check within the run
            if len(dates) != len(set(dates)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Run '{r.id}' contains duplicate observation dates.",
                )

            series_map[r.id] = pd.Series(returns, index=dates, name=r.id)
            run_lengths[r.id] = len(dates)

        # 5. Deterministic Date Alignment (Inner Join)
        df_raw = pd.DataFrame(series_map)
        aligned_df = df_raw.dropna(how="any").sort_index()

        T_aligned = len(aligned_df)
        min_raw = min(run_lengths.values())

        # Check observations sufficiency
        min_required_obs = max(20, 2 * req.n_slices)
        if T_aligned < min_required_obs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient synchronized observation dates (T={T_aligned}) across selected runs. "
                    f"At least {min_required_obs} aligned observations are required for {req.n_slices} time slices."
                ),
            )

        # 6. Audit alignment trimming & snapshot consistency
        alignment_warnings: list[str] = []
        if T_aligned < 0.8 * min_raw:
            alignment_warnings.append(
                f"Date alignment trimmed significant non-overlapping observations (aligned {T_aligned} of {min_raw} common days). "
                f"Strategy evaluation periods may diverge."
            )

        # Check snapshot consistency across runs
        snapshots = [r.snapshot_id for r in runs if r.snapshot_id]
        if snapshots and len(set(snapshots)) > 1:
            alignment_warnings.append(
                "Selected runs were executed against different dataset snapshots. Underlying market data divergence may affect results."
            )
        common_snapshot_id = snapshots[0] if (len(snapshots) == len(runs) and len(set(snapshots)) == 1) else None

        # 7. Execute numerical computation engine
        run_metadata = [
            {"run_id": r.id, "run_number": r.run_number}
            for r in runs
        ]

        diagnostics = compute_overfitting_diagnostics(
            returns_matrix=aligned_df.to_numpy(dtype=float),
            run_metadata=run_metadata,
            n_slices=req.n_slices,
            alpha=req.significance_level,
            annualization_factor=req.annualization_factor,
            experiment_id=exp.id,
            experiment_name=exp.name,
            strategy_type=exp.strategy_type,
            dataset_id=exp.dataset_id,
            snapshot_id=common_snapshot_id,
        )

        if alignment_warnings:
            diagnostics.warnings.extend(alignment_warnings)

        return diagnostics

