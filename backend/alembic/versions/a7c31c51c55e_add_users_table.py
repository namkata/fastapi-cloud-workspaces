"""Add users table

Revision ID: a7c31c51c55e
Revises: afc572f9a11e
Create Date: 2025-10-23 11:47:51.171673

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c31c51c55e'
down_revision: Union[str, Sequence[str], None] = 'afc572f9a11e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, comment="User's email address (unique)"),
        sa.Column('username', sa.String(50), nullable=False, comment="User's username (unique)"),
        sa.Column('full_name', sa.String(255), nullable=True, comment="User's full name"),
        sa.Column('hashed_password', sa.String(255), nullable=False, comment="Hashed password"),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False, comment="Whether the user account is active"),
        sa.Column('is_verified', sa.Boolean(), default=False, nullable=False, comment="Whether the user's email is verified"),
        sa.Column('is_superuser', sa.Boolean(), default=False, nullable=False, comment="Whether the user has superuser privileges"),
        sa.Column('avatar_url', sa.String(500), nullable=True, comment="URL to user's avatar image"),
        sa.Column('bio', sa.Text(), nullable=True, comment="User's biography"),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True, comment="Last login timestamp"),
        sa.Column('failed_login_attempts', sa.Integer(), default=0, nullable=False, comment="Number of consecutive failed login attempts"),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True, comment="Account locked until this timestamp"),
        sa.Column('email_verification_token', sa.String(255), nullable=True, comment="Token for email verification"),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True, comment="When email was verified"),
        sa.Column('password_reset_token', sa.String(255), nullable=True, comment="Token for password reset"),
        sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True, comment="When password reset token expires"),
    )

    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')

    # Drop users table
    op.drop_table('users')
