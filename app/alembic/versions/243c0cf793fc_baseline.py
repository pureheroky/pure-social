"""baseline

Revision ID: 243c0cf793fc
Revises: 
Create Date: 2025-07-02 22:26:51.888227

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func  # Add this import

# revision identifiers, used by Alembic.
revision: str = "243c0cf793fc"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('friendshipid', sa.Integer(), nullable=True),
        sa.Column('custom_url', sa.String(length=16), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=32), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create friendship table
    op.create_table(
        'friendship',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('friend_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('requested_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=True),
        sa.Column('accepted_at', sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=True),
        sa.PrimaryKeyConstraint('user_id', 'friend_id')
    )

def downgrade() -> None:
    # Drop friendship table
    op.drop_table('friendship')
    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')