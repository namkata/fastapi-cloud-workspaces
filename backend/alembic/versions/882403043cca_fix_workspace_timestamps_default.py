"""fix_workspace_timestamps_default

Revision ID: 882403043cca
Revises: 133cc5e3c04b
Create Date: 2025-10-23 13:44:32.505978

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '882403043cca'
down_revision: Union[str, Sequence[str], None] = '133cc5e3c04b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN with server_default directly
    # We need to recreate the table with proper defaults

    # Create new table with proper defaults
    op.create_table(
        'workspaces_new',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'archived', 'suspended', name='workspacestatus'), nullable=False, server_default='active'),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_members', sa.Integer(), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_workspace_owner_name')
    )

    # Copy data from old table to new table
    op.execute("""
        INSERT INTO workspaces_new (id, name, description, status, owner_id, is_public, max_members, avatar_url, created_at, updated_at)
        SELECT id, name, description, status, owner_id,
               COALESCE(is_public, 0) as is_public,
               max_members, avatar_url,
               COALESCE(created_at, datetime('now')) as created_at,
               COALESCE(updated_at, datetime('now')) as updated_at
        FROM workspaces
    """)

    # Drop old table
    op.drop_table('workspaces')

    # Rename new table to original name
    op.rename_table('workspaces_new', 'workspaces')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate original table without server defaults
    op.create_table(
        'workspaces_old',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'archived', 'suspended', name='workspacestatus'), nullable=False, server_default='active'),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_members', sa.Integer(), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_workspace_owner_name')
    )

    # Copy data back
    op.execute("""
        INSERT INTO workspaces_old (id, name, description, status, owner_id, is_public, max_members, avatar_url, created_at, updated_at)
        SELECT id, name, description, status, owner_id, is_public, max_members, avatar_url, created_at, updated_at
        FROM workspaces
    """)

    # Drop new table
    op.drop_table('workspaces')

    # Rename old table back
    op.rename_table('workspaces_old', 'workspaces')
