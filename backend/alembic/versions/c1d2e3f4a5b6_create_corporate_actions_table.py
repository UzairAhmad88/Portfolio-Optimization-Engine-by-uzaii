"""create_corporate_actions_table_and_pit_columns

Revision ID: c1d2e3f4a5b6
Revises: f5a6b7c8d9e0
Create Date: 2026-10-21 04:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create corporate_actions table and add PIT metadata columns to datasets."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Add columns to datasets if not present
    if "datasets" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("datasets")}
        if "point_in_time_status" not in existing_cols:
            op.add_column(
                "datasets",
                sa.Column("point_in_time_status", sa.String(length=50), nullable=False, server_default="unverified_legacy"),
            )
        if "calendar_version" not in existing_cols:
            op.add_column(
                "datasets",
                sa.Column("calendar_version", sa.String(length=50), nullable=True),
            )
        if "adjustment_policy_version" not in existing_cols:
            op.add_column(
                "datasets",
                sa.Column("adjustment_policy_version", sa.String(length=50), nullable=True),
            )

    # 2. Create corporate_actions table if not present
    if "corporate_actions" not in existing_tables:
        op.create_table(
            "corporate_actions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True),
            sa.Column("asset_id", sa.String(length=100), nullable=False),
            sa.Column("ticker", sa.String(length=50), nullable=False),
            sa.Column("market", sa.String(length=20), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("announcement_date", sa.Date(), nullable=True),
            sa.Column("ex_date", sa.Date(), nullable=True),
            sa.Column("record_date", sa.Date(), nullable=True),
            sa.Column("payment_date", sa.Date(), nullable=True),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("revision_id", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("is_point_in_time_verified", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("provenance_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_corporate_actions_asset_date", "corporate_actions", ["asset_id", "effective_date"])
        op.create_index("ix_corporate_actions_ticker_date", "corporate_actions", ["ticker", "market", "effective_date"])


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "corporate_actions" in existing_tables:
        op.drop_table("corporate_actions")

    if "datasets" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("datasets")}
        if "point_in_time_status" in existing_cols:
            op.drop_column("datasets", "point_in_time_status")
        if "calendar_version" in existing_cols:
            op.drop_column("datasets", "calendar_version")
        if "adjustment_policy_version" in existing_cols:
            op.drop_column("datasets", "adjustment_policy_version")
