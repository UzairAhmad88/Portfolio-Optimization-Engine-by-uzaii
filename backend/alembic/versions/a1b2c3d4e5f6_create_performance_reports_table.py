"""create_performance_reports_table

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-10-18 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "performance_reports" not in existing_tables:
        op.create_table(
            "performance_reports",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("backtest_id", sa.String(length=36), sa.ForeignKey("backtest_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("benchmark_asset", sa.String(length=100), nullable=False),
            sa.Column("risk_free_rate", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
            sa.Column("metrics_json", sa.Text(), nullable=True),
            sa.Column("contributions_json", sa.Text(), nullable=True),
            sa.Column("timeseries_json", sa.Text(), nullable=True),
            sa.Column("warnings_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_performance_reports_id", "performance_reports", ["id"])
        op.create_index("ix_performance_reports_user_id", "performance_reports", ["user_id"])
        op.create_index("ix_performance_reports_dataset_id", "performance_reports", ["dataset_id"])
        op.create_index("ix_performance_reports_backtest_id", "performance_reports", ["backtest_id"])
        op.create_index("ix_performance_reports_created_at", "performance_reports", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_performance_reports_created_at", table_name="performance_reports")
    op.drop_index("ix_performance_reports_backtest_id", table_name="performance_reports")
    op.drop_index("ix_performance_reports_dataset_id", table_name="performance_reports")
    op.drop_index("ix_performance_reports_user_id", table_name="performance_reports")
    op.drop_index("ix_performance_reports_id", table_name="performance_reports")
    op.drop_table("performance_reports")
