"""create_scenario_runs_table

Revision ID: e4f5a6b7c8d9
Revises: 8993dbd79e8a
Create Date: 2026-10-18 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = '8993dbd79e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "scenario_runs" not in existing_tables:
        op.create_table(
            "scenario_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("scenario_type", sa.String(length=50), nullable=False),
            sa.Column("initial_capital", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("percentage_change", sa.Float(), nullable=False),
            sa.Column("absolute_change", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
            sa.Column("request_config_json", sa.Text(), nullable=True),
            sa.Column("summary_metrics_json", sa.Text(), nullable=True),
            sa.Column("contributions_json", sa.Text(), nullable=True),
            sa.Column("warnings_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_scenario_runs_id", "scenario_runs", ["id"])
        op.create_index("ix_scenario_runs_user_id", "scenario_runs", ["user_id"])
        op.create_index("ix_scenario_runs_dataset_id", "scenario_runs", ["dataset_id"])
        op.create_index("ix_scenario_runs_created_at", "scenario_runs", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_scenario_runs_created_at", table_name="scenario_runs")
    op.drop_index("ix_scenario_runs_dataset_id", table_name="scenario_runs")
    op.drop_index("ix_scenario_runs_user_id", table_name="scenario_runs")
    op.drop_index("ix_scenario_runs_id", table_name="scenario_runs")
    op.drop_table("scenario_runs")
