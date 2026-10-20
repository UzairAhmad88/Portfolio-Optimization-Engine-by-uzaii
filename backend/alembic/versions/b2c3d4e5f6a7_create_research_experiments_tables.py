"""create_research_experiments_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-18 02:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "research_experiments" not in existing_tables:
        op.create_table(
            "research_experiments",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("strategy_type", sa.String(length=50), nullable=False),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_research_experiments_id", "research_experiments", ["id"])
        op.create_index("ix_research_experiments_user_id", "research_experiments", ["user_id"])
        op.create_index("ix_research_experiments_dataset_id", "research_experiments", ["dataset_id"])
        op.create_index("ix_research_experiments_config_fingerprint", "research_experiments", ["config_fingerprint"])
        op.create_index("ix_research_experiments_created_at", "research_experiments", ["created_at"])

    if "research_experiment_runs" not in existing_tables:
        op.create_table(
            "research_experiment_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("experiment_id", sa.String(length=36), sa.ForeignKey("research_experiments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("run_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("dataset_version_hash", sa.String(length=64), nullable=True),
            sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
            sa.Column("backtest_id", sa.String(length=36), sa.ForeignKey("backtest_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("performance_report_id", sa.String(length=36), sa.ForeignKey("performance_reports.id", ondelete="SET NULL"), nullable=True),
            sa.Column("risk_simulation_id", sa.String(length=36), sa.ForeignKey("risk_simulation_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("summary_kpis_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_research_experiment_runs_id", "research_experiment_runs", ["id"])
        op.create_index("ix_research_experiment_runs_experiment_id", "research_experiment_runs", ["experiment_id"])
        op.create_index("ix_research_experiment_runs_user_id", "research_experiment_runs", ["user_id"])
        op.create_index("ix_research_experiment_runs_backtest_id", "research_experiment_runs", ["backtest_id"])
        op.create_index("ix_research_experiment_runs_performance_report_id", "research_experiment_runs", ["performance_report_id"])
        op.create_index("ix_research_experiment_runs_risk_simulation_id", "research_experiment_runs", ["risk_simulation_id"])
        op.create_index("ix_research_experiment_runs_created_at", "research_experiment_runs", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_research_experiment_runs_created_at", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_risk_simulation_id", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_performance_report_id", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_backtest_id", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_user_id", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_experiment_id", table_name="research_experiment_runs")
    op.drop_index("ix_research_experiment_runs_id", table_name="research_experiment_runs")
    op.drop_table("research_experiment_runs")

    op.drop_index("ix_research_experiments_created_at", table_name="research_experiments")
    op.drop_index("ix_research_experiments_config_fingerprint", table_name="research_experiments")
    op.drop_index("ix_research_experiments_dataset_id", table_name="research_experiments")
    op.drop_index("ix_research_experiments_user_id", table_name="research_experiments")
    op.drop_index("ix_research_experiments_id", table_name="research_experiments")
    op.drop_table("research_experiments")
