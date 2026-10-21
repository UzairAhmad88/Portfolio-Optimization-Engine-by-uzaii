"""add_frozen_payload_to_dataset_snapshots

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-10-21 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add frozen_payload_json to dataset_snapshots."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "dataset_snapshots" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("dataset_snapshots")}
        if "frozen_payload_json" not in existing_cols:
            with op.batch_alter_table("dataset_snapshots") as batch_op:
                batch_op.add_column(sa.Column("frozen_payload_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema: remove frozen_payload_json from dataset_snapshots."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "dataset_snapshots" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("dataset_snapshots")}
        if "frozen_payload_json" in existing_cols:
            with op.batch_alter_table("dataset_snapshots") as batch_op:
                batch_op.drop_column("frozen_payload_json")
