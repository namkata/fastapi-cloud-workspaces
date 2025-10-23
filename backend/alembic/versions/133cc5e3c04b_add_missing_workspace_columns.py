"""Add missing workspace columns

Revision ID: 133cc5e3c04b
Revises: afc572f9a11e
Create Date: 2025-10-23 13:30:46.148540

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '133cc5e3c04b'
down_revision: Union[str, Sequence[str], None] = ('afc572f9a11e', 'a7c31c51c55e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing columns to workspaces table
    op.add_column('workspaces', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('workspaces', sa.Column('max_members', sa.Integer(), nullable=True))
    op.add_column('workspaces', sa.Column('avatar_url', sa.String(500), nullable=True))

    # For SQLite, we need to recreate the workspace_roles table to make workspace_id nullable
    # First, create a temporary table with the new structure
    op.create_table(
        'workspace_roles_temp',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('workspace_id', sa.UUID(), nullable=True),  # Now nullable
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_workspace_role_name_workspace')
    )

    # Copy data from old table to new table
    op.execute("""
        INSERT INTO workspace_roles_temp (id, name, description, permissions, is_system_role, workspace_id, created_at, updated_at)
        SELECT id, name, description, permissions, is_system_role, workspace_id, created_at, updated_at
        FROM workspace_roles
    """)

    # Drop the old table and rename the new one
    op.drop_table('workspace_roles')
    op.rename_table('workspace_roles_temp', 'workspace_roles')

    # Recreate the index
    op.create_index('ix_workspace_roles_workspace_id', 'workspace_roles', ['workspace_id'])

    # Update workspace_members table to use role_id instead of role enum
    op.add_column('workspace_members', sa.Column('role_id', sa.UUID(), nullable=True))
    op.add_column('workspace_members', sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True))

    # Create foreign key constraint for role_id
    op.create_foreign_key('fk_workspace_members_role_id', 'workspace_members', 'workspace_roles', ['role_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key constraint
    op.drop_constraint('fk_workspace_members_role_id', 'workspace_members', type_='foreignkey')

    # Remove added columns from workspace_members
    op.drop_column('workspace_members', 'invited_at')
    op.drop_column('workspace_members', 'role_id')

    # Revert workspace_roles workspace_id to not nullable
    op.alter_column('workspace_roles', 'workspace_id', nullable=False)

    # Remove added columns from workspaces
    op.drop_column('workspaces', 'avatar_url')
    op.drop_column('workspaces', 'max_members')
    op.drop_column('workspaces', 'is_public')
