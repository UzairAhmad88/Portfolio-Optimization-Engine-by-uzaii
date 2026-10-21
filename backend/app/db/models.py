"""
SQLAlchemy relational models for persistent market datasets, assets, and price bars.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserModel(Base):
    """
    Normalized user account identity model for authentication and authorization.
    """

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=True)
    role = Column(String(50), default="researcher", nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    datasets = relationship("DatasetModel", back_populates="owner")


class DatasetModel(Base):
    """
    Durable persistent record of an uploaded and registered market dataset.
    """

    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_shared = Column(Boolean, default=False, nullable=False)
    filename = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    source_type = Column(String(50), default="csv_upload", nullable=False)
    content_sha256 = Column(String(64), nullable=False, index=True)
    rows_examined = Column(Integer, nullable=False)
    valid_rows = Column(Integer, nullable=False)
    rejected_rows = Column(Integer, nullable=False)
    status = Column(String(30), default="completed", nullable=False)  # completed, pending, failed
    point_in_time_status = Column(String(50), default="unverified_legacy", nullable=False)
    calendar_version = Column(String(50), nullable=True)
    adjustment_policy_version = Column(String(50), nullable=True)
    errors_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)

    owner = relationship("UserModel", back_populates="datasets")
    assets = relationship(
        "AssetModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    price_bars = relationship(
        "PriceBarModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    corporate_actions = relationship(
        "CorporateActionModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    snapshots = relationship(
        "DatasetSnapshotModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def get_errors(self) -> list[dict[str, Any]]:
        if not self.errors_json:
            return []
        try:
            return json.loads(self.errors_json)
        except Exception:
            return []

    def get_warnings(self) -> list[dict[str, Any]]:
        if not self.warnings_json:
            return []
        try:
            return json.loads(self.warnings_json)
        except Exception:
            return []


class AssetModel(Base):
    """
    Asset metadata summarizing availability, dates, and observation counts per dataset.
    """

    __tablename__ = "dataset_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(String(100), nullable=False, index=True)  # Composite TICKER:MARKET
    ticker = Column(String(50), nullable=False, index=True)
    market = Column(String(20), nullable=False)
    currency = Column(String(10), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    observation_count = Column(Integer, nullable=False)

    dataset = relationship("DatasetModel", back_populates="assets")

    __table_args__ = (
        UniqueConstraint("dataset_id", "asset_id", name="uq_dataset_asset"),
        Index("ix_dataset_asset_ticker", "dataset_id", "ticker"),
    )


class PriceBarModel(Base):
    """
    Individual daily adjusted historical price bar.
    """

    __tablename__ = "price_bars"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(String(100), nullable=False, index=True)
    ticker = Column(String(50), nullable=False, index=True)
    market = Column(String(20), nullable=False)
    currency = Column(String(10), nullable=False)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=False)
    adj_close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    dataset = relationship("DatasetModel", back_populates="price_bars")

    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "ticker", "market", "date",
            name="uq_dataset_ticker_market_date"
        ),
        Index("ix_price_bars_dataset_date", "dataset_id", "date"),
        Index("ix_price_bars_dataset_ticker_date", "dataset_id", "ticker", "date"),
    )


class CorporateActionModel(Base):
    """
    Persistent record of a corporate action event (stock split, reverse split, cash dividend, symbol change).
    """

    __tablename__ = "corporate_actions"

    id = Column(String(36), primary_key=True, index=True)
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    asset_id = Column(String(100), nullable=False, index=True)
    ticker = Column(String(50), nullable=False, index=True)
    market = Column(String(20), nullable=False)
    event_type = Column(String(50), nullable=False)  # stock_split, reverse_split, cash_dividend, etc.
    effective_date = Column(Date, nullable=False, index=True)
    announcement_date = Column(Date, nullable=True)
    ex_date = Column(Date, nullable=True)
    record_date = Column(Date, nullable=True)
    payment_date = Column(Date, nullable=True)
    value = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    source = Column(String(100), nullable=False)
    revision_id = Column(String(100), nullable=True)
    status = Column(String(30), default="active", nullable=False)  # active, superseded, cancelled
    is_point_in_time_verified = Column(Boolean, default=False, nullable=False)
    provenance_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    dataset = relationship("DatasetModel", back_populates="corporate_actions")

    __table_args__ = (
        Index("ix_corporate_actions_asset_date", "asset_id", "effective_date"),
        Index("ix_corporate_actions_ticker_date", "ticker", "market", "effective_date"),
    )


class DatasetSnapshotModel(Base):
    """
    Persistent immutable snapshot record binding a dataset's observations,
    corporate actions, point-in-time status, and policies to a cryptographic manifest.
    """

    __tablename__ = "dataset_snapshots"

    id = Column(String(36), primary_key=True, index=True)
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tag = Column(String(100), nullable=True, index=True)  # e.g. "baseline_2024_q1"
    description = Column(Text, nullable=True)
    snapshot_type = Column(String(30), default="manual", nullable=False)  # "manual", "auto_backtest", "auto_experiment"
    manifest_sha256 = Column(String(64), nullable=False, index=True)
    manifest_json = Column(Text, nullable=False)
    as_of_date = Column(Date, nullable=True)
    point_in_time_status = Column(String(50), default="unverified_legacy", nullable=False)
    calendar_version = Column(String(50), nullable=True)
    adjustment_policy_version = Column(String(50), nullable=True)
    is_frozen = Column(Boolean, default=True, nullable=False)
    total_bars_count = Column(Integer, nullable=False, default=0)
    total_actions_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    frozen_payload_json = Column(Text, nullable=True)

    dataset = relationship("DatasetModel", back_populates="snapshots")
    user = relationship("UserModel", backref="dataset_snapshots")

    __table_args__ = (
        Index("ix_dataset_snapshots_dataset_tag", "dataset_id", "tag"),
        Index("ix_dataset_snapshots_created_at", "created_at"),
    )

    def get_manifest(self) -> dict[str, Any]:
        if not self.manifest_json:
            return {}
        try:
            return json.loads(self.manifest_json)
        except Exception:
            return {}

    def get_frozen_payload(self) -> dict[str, Any]:
        if not self.frozen_payload_json:
            return {}
        try:
            return json.loads(self.frozen_payload_json)
        except Exception:
            return {}


class BacktestRunModel(Base):
    """
    Persistent record of an executed portfolio strategy backtest simulation.
    """

    __tablename__ = "backtest_runs"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id = Column(
        String(36),
        ForeignKey("dataset_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(150), nullable=False)
    strategy_type = Column(String(50), nullable=False)  # target_weights, equal_weight, walk_forward_optimization
    rebalance_frequency = Column(String(30), nullable=False)  # buy_and_hold, daily, weekly, monthly, quarterly
    initial_capital = Column(Float, nullable=False, default=100000.0)
    transaction_cost_bps = Column(Float, nullable=False, default=10.0)
    slippage_bps = Column(Float, nullable=False, default=5.0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="completed")  # completed, failed
    strategy_config_json = Column(Text, nullable=True)
    summary_metrics_json = Column(Text, nullable=True)
    equity_curve_json = Column(Text, nullable=True)
    rebalance_events_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("UserModel", backref="backtest_runs")
    dataset = relationship("DatasetModel", backref="backtest_runs")
    snapshot = relationship("DatasetSnapshotModel", backref="backtest_runs")

    def get_strategy_config(self) -> dict[str, Any]:
        if not self.strategy_config_json:
            return {}
        try:
            return json.loads(self.strategy_config_json)
        except Exception:
            return {}

    def get_summary_metrics(self) -> dict[str, Any]:
        if not self.summary_metrics_json:
            return {}
        try:
            return json.loads(self.summary_metrics_json)
        except Exception:
            return {}

    def get_equity_curve(self) -> list[dict[str, Any]]:
        if not self.equity_curve_json:
            return []
        try:
            return json.loads(self.equity_curve_json)
        except Exception:
            return []

    def get_rebalance_events(self) -> list[dict[str, Any]]:
        if not self.rebalance_events_json:
            return []
        try:
            return json.loads(self.rebalance_events_json)
        except Exception:
            return []


class ScenarioRunModel(Base):
    """
    Persistent record of an executed portfolio scenario analysis or stress test.
    """

    __tablename__ = "scenario_runs"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(150), nullable=False)
    scenario_type = Column(String(50), nullable=False)  # custom_asset_shock, historical_window, covariance_stress
    initial_capital = Column(Float, nullable=False, default=100000.0)
    percentage_change = Column(Float, nullable=False)
    absolute_change = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    status = Column(String(30), nullable=False, default="completed")
    request_config_json = Column(Text, nullable=True)
    summary_metrics_json = Column(Text, nullable=True)
    contributions_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("UserModel", backref="scenario_runs")
    dataset = relationship("DatasetModel", backref="scenario_runs")

    def get_request_config(self) -> dict[str, Any]:
        if not self.request_config_json:
            return {}
        try:
            return json.loads(self.request_config_json)
        except Exception:
            return {}

    def get_summary_metrics(self) -> dict[str, Any]:
        if not self.summary_metrics_json:
            return {}
        try:
            return json.loads(self.summary_metrics_json)
        except Exception:
            return {}

    def get_contributions(self) -> list[dict[str, Any]]:
        if not self.contributions_json:
            return []
        try:
            return json.loads(self.contributions_json)
        except Exception:
            return []

    def get_warnings(self) -> list[str]:
        if not self.warnings_json:
            return []
        try:
            return json.loads(self.warnings_json)
        except Exception:
            return []


class RiskSimulationRunModel(Base):
    """
    Persistent record of an executed Monte Carlo portfolio risk simulation.
    """

    __tablename__ = "risk_simulation_runs"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(150), nullable=False)
    distribution = Column(String(50), nullable=False)  # multivariate_normal, multivariate_student_t
    rebalance_policy = Column(String(50), nullable=False)  # buy_and_hold, constant_weights
    horizon_days = Column(Integer, nullable=False, default=21)
    num_paths = Column(Integer, nullable=False, default=1000)
    initial_capital = Column(Float, nullable=False, default=100000.0)
    expected_terminal_return = Column(Float, nullable=False, default=0.0)
    var_95 = Column(Float, nullable=False, default=0.0)
    cvar_95 = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="USD")
    status = Column(String(30), nullable=False, default="completed")
    request_config_json = Column(Text, nullable=True)
    summary_metrics_json = Column(Text, nullable=True)
    distribution_bins_json = Column(Text, nullable=True)
    trajectory_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("UserModel", backref="risk_simulation_runs")
    dataset = relationship("DatasetModel", backref="risk_simulation_runs")

    def get_request_config(self) -> dict[str, Any]:
        if not self.request_config_json:
            return {}
        try:
            return json.loads(self.request_config_json)
        except Exception:
            return {}

    def get_summary_metrics(self) -> dict[str, Any]:
        if not self.summary_metrics_json:
            return {}
        try:
            return json.loads(self.summary_metrics_json)
        except Exception:
            return {}

    def get_distribution_bins(self) -> list[dict[str, Any]]:
        if not self.distribution_bins_json:
            return []
        try:
            return json.loads(self.distribution_bins_json)
        except Exception:
            return []

    def get_trajectory(self) -> list[dict[str, Any]]:
        if not self.trajectory_json:
            return []
        try:
            return json.loads(self.trajectory_json)
        except Exception:
            return []

    def get_warnings(self) -> list[str]:
        if not self.warnings_json:
            return []
        try:
            return json.loads(self.warnings_json)
        except Exception:
            return []


class PerformanceReportModel(Base):
    """
    Persistent record of an executed portfolio performance and benchmark attribution report.
    """

    __tablename__ = "performance_reports"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    backtest_id = Column(
        String(36),
        ForeignKey("backtest_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(150), nullable=False)
    benchmark_asset = Column(String(100), nullable=False)
    risk_free_rate = Column(Float, nullable=False, default=0.0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="completed")
    metrics_json = Column(Text, nullable=True)
    contributions_json = Column(Text, nullable=True)
    timeseries_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("UserModel", backref="performance_reports")
    dataset = relationship("DatasetModel", backref="performance_reports")
    backtest = relationship("BacktestRunModel", backref="performance_reports")

    def get_metrics(self) -> dict[str, Any]:
        if not self.metrics_json:
            return {}
        try:
            return json.loads(self.metrics_json)
        except Exception:
            return {}

    def get_contributions(self) -> list[dict[str, Any]]:
        if not self.contributions_json:
            return []
        try:
            return json.loads(self.contributions_json)
        except Exception:
            return []

    def get_timeseries(self) -> list[dict[str, Any]]:
        if not self.timeseries_json:
            return []
        try:
            return json.loads(self.timeseries_json)
        except Exception:
            return []

    def get_warnings(self) -> list[str]:
        if not self.warnings_json:
            return []
        try:
            return json.loads(self.warnings_json)
        except Exception:
            return []


class ResearchExperimentModel(Base):
    """
    Persistent record of a portfolio research experiment definition and canonical configuration.
    """

    __tablename__ = "research_experiments"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)
    config_json = Column(Text, nullable=False)
    config_fingerprint = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("UserModel", backref="research_experiments")
    dataset = relationship("DatasetModel", backref="research_experiments")
    runs = relationship(
        "ResearchExperimentRunModel",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ResearchExperimentRunModel.run_number",
    )

    def get_config(self) -> dict[str, Any]:
        if not self.config_json:
            return {}
        try:
            return json.loads(self.config_json)
        except Exception:
            return {}


class ResearchExperimentRunModel(Base):
    """
    Persistent record of an individual execution run of a research experiment.
    """

    __tablename__ = "research_experiment_runs"

    id = Column(String(36), primary_key=True, index=True)
    experiment_id = Column(
        String(36),
        ForeignKey("research_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_number = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="pending")
    dataset_version_hash = Column(String(64), nullable=True)
    snapshot_id = Column(
        String(36),
        ForeignKey("dataset_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    config_fingerprint = Column(String(64), nullable=False)
    execution_duration_ms = Column(Integer, nullable=True)
    backtest_id = Column(
        String(36),
        ForeignKey("backtest_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    performance_report_id = Column(
        String(36),
        ForeignKey("performance_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_simulation_id = Column(
        String(36),
        ForeignKey("risk_simulation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary_kpis_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    experiment = relationship("ResearchExperimentModel", back_populates="runs")
    user = relationship("UserModel", backref="research_experiment_runs")
    backtest = relationship("BacktestRunModel", backref="research_experiment_runs")
    performance_report = relationship("PerformanceReportModel", backref="research_experiment_runs")
    risk_simulation = relationship("RiskSimulationRunModel", backref="research_experiment_runs")
    snapshot = relationship("DatasetSnapshotModel", backref="research_experiment_runs")

    def get_summary_kpis(self) -> dict[str, Any]:
        if not self.summary_kpis_json:
            return {}
        try:
            return json.loads(self.summary_kpis_json)
        except Exception:
            return {}


