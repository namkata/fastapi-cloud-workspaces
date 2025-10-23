"""fix_workspace_members_complete

Revision ID: 05497957d66c
Revises: 882403043cca
Create Date: 2025-10-23 14:03:36.671566

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '05497957d66c'
down_revision: Union[str, Sequence[str], None] = '882403043cca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create a completely new workspace_members table with all required columns and proper defaults
    op.create_table('workspace_members_new',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'member', 'viewer', name='workspacerole'), nullable=False, server_default='viewer'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invited_by', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('role_id', sa.UUID(), nullable=True),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['workspace_roles.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy existing data with proper timestamp handling
    op.execute("""
        INSERT INTO workspace_members_new
        (id, user_id, workspace_id, role, joined_at, invited_by, is_active, created_at, updated_at, role_id, invited_at)
        SELECT id, user_id, workspace_id, role, joined_at, invited_by, is_active,
               COALESCE(created_at, CURRENT_TIMESTAMP),
               COALESCE(updated_at, CURRENT_TIMESTAMP),
               role_id, invited_at
        FROM workspace_members
    """)

    # Drop the old table and rename the new one
    op.drop_table('workspace_members')
    op.rename_table('workspace_members_new', 'workspace_members')


def downgrade() -> None:
    """Downgrade schema."""
    # Create the old table structure (without proper defaults)
    op.create_table('workspace_members_old',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'member', 'viewer', name='workspacerole'), nullable=False, server_default='viewer'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invited_by', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('role_id', sa.UUID(), nullable=True),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data back
    op.execute("""
        INSERT INTO workspace_members_old
        (id, user_id, workspace_id, role, joined_at, invited_by, is_active, created_at, updated_at, role_id, invited_at)
        SELECT id, user_id, workspace_id, role, joined_at, invited_by, is_active, created_at, updated_at, role_id, invited_at
        FROM workspace_members
    """)

    # Drop the new table and rename the old one
    op.drop_table('workspace_members')
    op.rename_table('workspace_members_old', 'workspace_members')
