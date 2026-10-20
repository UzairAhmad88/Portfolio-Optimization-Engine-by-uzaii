"""create_risk_simulation_runs_table

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-10-18 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "risk_simulation_runs" not in existing_tables:
        op.create_table(
            "risk_simulation_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("distribution", sa.String(length=50), nullable=False),
            sa.Column("rebalance_policy", sa.String(length=50), nullable=False),
            sa.Column("horizon_days", sa.Integer(), nullable=False, server_default="21"),
            sa.Column("num_paths", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("initial_capital", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("expected_terminal_return", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("var_95", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("cvar_95", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
            sa.Column("request_config_json", sa.Text(), nullable=True),
            sa.Column("summary_metrics_json", sa.Text(), nullable=True),
            sa.Column("distribution_bins_json", sa.Text(), nullable=True),
            sa.Column("trajectory_json", sa.Text(), nullable=True),
            sa.Column("warnings_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_risk_simulation_runs_id", "risk_simulation_runs", ["id"])
        op.create_index("ix_risk_simulation_runs_user_id", "risk_simulation_runs", ["user_id"])
        op.create_index("ix_risk_simulation_runs_dataset_id", "risk_simulation_runs", ["dataset_id"])
        op.create_index("ix_risk_simulation_runs_created_at", "risk_simulation_runs", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_risk_simulation_runs_created_at", table_name="risk_simulation_runs")
    op.drop_index("ix_risk_simulation_runs_dataset_id", table_name="risk_simulation_runs")
    op.drop_index("ix_risk_simulation_runs_user_id", table_name="risk_simulation_runs")
    op.drop_index("ix_risk_simulation_runs_id", table_name="risk_simulation_runs")
    op.drop_table("risk_simulation_runs")
