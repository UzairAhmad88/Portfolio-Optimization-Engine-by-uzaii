"""create_dataset_snapshots_table_and_run_linkages

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-10-21 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create dataset_snapshots table and add snapshot_id to backtest_runs and research_experiment_runs."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create dataset_snapshots table if not present
    if "dataset_snapshots" not in existing_tables:
        op.create_table(
            "dataset_snapshots",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tag", sa.String(length=100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("snapshot_type", sa.String(length=30), nullable=False, server_default="manual"),
            sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
            sa.Column("manifest_json", sa.Text(), nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=True),
            sa.Column("point_in_time_status", sa.String(length=50), nullable=False, server_default="unverified_legacy"),
            sa.Column("calendar_version", sa.String(length=50), nullable=True),
            sa.Column("adjustment_policy_version", sa.String(length=50), nullable=True),
            sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("total_bars_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_actions_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_dataset_snapshots_dataset_id", "dataset_snapshots", ["dataset_id"])
        op.create_index("ix_dataset_snapshots_user_id", "dataset_snapshots", ["user_id"])
        op.create_index("ix_dataset_snapshots_manifest_sha256", "dataset_snapshots", ["manifest_sha256"])
        op.create_index("ix_dataset_snapshots_dataset_tag", "dataset_snapshots", ["dataset_id", "tag"])
        op.create_index("ix_dataset_snapshots_created_at", "dataset_snapshots", ["created_at"])

    # 2. Add nullable snapshot_id to backtest_runs
    if "backtest_runs" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("backtest_runs")}
        if "snapshot_id" not in existing_cols:
            with op.batch_alter_table("backtest_runs") as batch_op:
                batch_op.add_column(sa.Column("snapshot_id", sa.String(length=36), nullable=True))
                batch_op.create_foreign_key(
                    "fk_backtest_runs_snapshot_id",
                    "dataset_snapshots",
                    ["snapshot_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch_op.create_index("ix_backtest_runs_snapshot_id", ["snapshot_id"])

    # 3. Add nullable snapshot_id to research_experiment_runs
    if "research_experiment_runs" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("research_experiment_runs")}
        if "snapshot_id" not in existing_cols:
            with op.batch_alter_table("research_experiment_runs") as batch_op:
                batch_op.add_column(sa.Column("snapshot_id", sa.String(length=36), nullable=True))
                batch_op.create_foreign_key(
                    "fk_research_experiment_runs_snapshot_id",
                    "dataset_snapshots",
                    ["snapshot_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch_op.create_index("ix_research_experiment_runs_snapshot_id", ["snapshot_id"])


def downgrade() -> None:
    """Downgrade schema: remove linkages and drop dataset_snapshots table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "research_experiment_runs" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("research_experiment_runs")}
        if "snapshot_id" in existing_cols:
            with op.batch_alter_table("research_experiment_runs") as batch_op:
                batch_op.drop_constraint("fk_research_experiment_runs_snapshot_id", type_="foreignkey")
                batch_op.drop_index("ix_research_experiment_runs_snapshot_id")
                batch_op.drop_column("snapshot_id")

    if "backtest_runs" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("backtest_runs")}
        if "snapshot_id" in existing_cols:
            with op.batch_alter_table("backtest_runs") as batch_op:
                batch_op.drop_constraint("fk_backtest_runs_snapshot_id", type_="foreignkey")
                batch_op.drop_index("ix_backtest_runs_snapshot_id")
                batch_op.drop_column("snapshot_id")

    if "dataset_snapshots" in existing_tables:
        op.drop_index("ix_dataset_snapshots_created_at", table_name="dataset_snapshots")
        op.drop_index("ix_dataset_snapshots_dataset_tag", table_name="dataset_snapshots")
        op.drop_index("ix_dataset_snapshots_manifest_sha256", table_name="dataset_snapshots")
        op.drop_index("ix_dataset_snapshots_user_id", table_name="dataset_snapshots")
        op.drop_index("ix_dataset_snapshots_dataset_id", table_name="dataset_snapshots")
        op.drop_table("dataset_snapshots")
