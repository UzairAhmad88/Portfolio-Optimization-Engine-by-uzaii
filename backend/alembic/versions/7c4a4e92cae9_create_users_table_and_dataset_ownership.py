"""create_users_table_and_dataset_ownership

Revision ID: 7c4a4e92cae9
Revises: 0a14be571daa
Create Date: 2026-10-17 20:54:48.489066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4a4e92cae9'
down_revision: Union[str, Sequence[str], None] = '0a14be571daa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add users table and dataset ownership columns."""
    # Create users table if not exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('full_name', sa.String(length=150), nullable=True),
            sa.Column('role', sa.String(length=50), nullable=False, server_default='researcher'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    # Add user_id and is_shared to datasets via batch mode for SQLite/PostgreSQL compatibility
    dataset_cols = [c['name'] for c in inspector.get_columns('datasets')]
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        if 'user_id' not in dataset_cols:
            batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
            batch_op.create_index(op.f('ix_datasets_user_id'), ['user_id'], unique=False)
            batch_op.create_foreign_key(
                'fk_datasets_user_id_users',
                'users',
                ['user_id'],
                ['id'],
                ondelete='SET NULL'
            )
        if 'is_shared' not in dataset_cols:
            batch_op.add_column(
                sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    """Downgrade schema: remove dataset ownership and drop users table."""
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.drop_constraint('fk_datasets_user_id_users', type_='foreignkey')
        batch_op.drop_index(op.f('ix_datasets_user_id'))
        batch_op.drop_column('is_shared')
        batch_op.drop_column('user_id')

    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
