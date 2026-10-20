"""create_backtest_runs_table

Revision ID: 8993dbd79e8a
Revises: 7c4a4e92cae9
Create Date: 2026-10-17 21:28:29.569235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8993dbd79e8a'
down_revision: Union[str, Sequence[str], None] = '7c4a4e92cae9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "backtest_runs" not in existing_tables:
        op.create_table(
            "backtest_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("strategy_type", sa.String(length=50), nullable=False),
            sa.Column("rebalance_frequency", sa.String(length=30), nullable=False),
            sa.Column("initial_capital", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("transaction_cost_bps", sa.Float(), nullable=False, server_default="10.0"),
            sa.Column("slippage_bps", sa.Float(), nullable=False, server_default="5.0"),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
            sa.Column("strategy_config_json", sa.Text(), nullable=True),
            sa.Column("summary_metrics_json", sa.Text(), nullable=True),
            sa.Column("equity_curve_json", sa.Text(), nullable=True),
            sa.Column("rebalance_events_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_backtest_runs_id", "backtest_runs", ["id"])
        op.create_index("ix_backtest_runs_user_id", "backtest_runs", ["user_id"])
        op.create_index("ix_backtest_runs_dataset_id", "backtest_runs", ["dataset_id"])
        op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])



def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_dataset_id", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_user_id", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_id", table_name="backtest_runs")
    op.drop_table("backtest_runs")

