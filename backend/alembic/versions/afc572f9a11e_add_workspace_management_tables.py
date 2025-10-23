"""Add workspace management tables

Revision ID: afc572f9a11e
Revises:
Create Date: 2025-10-23 11:06:33.582084

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'afc572f9a11e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create workspace status enum
    workspace_status_enum = sa.Enum('active', 'archived', 'suspended', name='workspacestatus')
    workspace_status_enum.create(op.get_bind())

    # Create workspace role enum
    workspace_role_enum = sa.Enum('admin', 'editor', 'viewer', name='workspacerole')
    workspace_role_enum.create(op.get_bind())

    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', workspace_status_enum, nullable=False, server_default='active'),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_workspace_owner_name')
    )

    # Create workspace_roles table
    op.create_table(
        'workspace_roles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_workspace_role_name')
    )

    # Create workspace_members table
    op.create_table(
        'workspace_members',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('role', workspace_role_enum, nullable=False, server_default='viewer'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invited_by', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'workspace_id', name='uq_workspace_member')
    )

    # Create indexes for better performance
    op.create_index('ix_workspaces_owner_id', 'workspaces', ['owner_id'])
    op.create_index('ix_workspaces_status', 'workspaces', ['status'])
    op.create_index('ix_workspace_members_user_id', 'workspace_members', ['user_id'])
    op.create_index('ix_workspace_members_workspace_id', 'workspace_members', ['workspace_id'])
    op.create_index('ix_workspace_members_role', 'workspace_members', ['role'])
    op.create_index('ix_workspace_roles_workspace_id', 'workspace_roles', ['workspace_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_workspace_roles_workspace_id', 'workspace_roles')
    op.drop_index('ix_workspace_members_role', 'workspace_members')
    op.drop_index('ix_workspace_members_workspace_id', 'workspace_members')
    op.drop_index('ix_workspace_members_user_id', 'workspace_members')
    op.drop_index('ix_workspaces_status', 'workspaces')
    op.drop_index('ix_workspaces_owner_id', 'workspaces')

    # Drop tables
    op.drop_table('workspace_members')
    op.drop_table('workspace_roles')
    op.drop_table('workspaces')

    # Drop enums
    sa.Enum(name='workspacerole').drop(op.get_bind())
    sa.Enum(name='workspacestatus').drop(op.get_bind())
