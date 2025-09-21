"""Add profile_pic

Revision ID: 272927f5c1bc
Revises: 243c0cf793fc
Create Date: 2025-07-02 22:27:44.842896

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '272927f5c1bc'
down_revision: Union[str, Sequence[str], None] = '243c0cf793fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # Add profile_pic to users
    op.add_column('users', sa.Column('profile_pic', sa.String(length=256), nullable=True))
    # Update nullability of users columns if needed
    op.alter_column('users', 'custom_url',
                    existing_type=sa.VARCHAR(length=16),
                    nullable=False)
    op.alter_column('users', 'age',
                    existing_type=sa.INTEGER(),
                    nullable=False)
    op.alter_column('users', 'username',
                    existing_type=sa.VARCHAR(length=32),
                    nullable=False)
    op.alter_column('users', 'password_hash',
                    existing_type=sa.TEXT(),
                    nullable=False)
    op.alter_column('users', 'email',
                    existing_type=sa.TEXT(),
                    nullable=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('users', 'email',
                    existing_type=sa.TEXT(),
                    nullable=True)
    op.alter_column('users', 'password_hash',
                    existing_type=sa.TEXT(),
                    nullable=True)
    op.alter_column('users', 'username',
                    existing_type=sa.VARCHAR(length=32),
                    nullable=True)
    op.alter_column('users', 'age',
                    existing_type=sa.INTEGER(),
                    nullable=True)
    op.alter_column('users', 'custom_url',
                    existing_type=sa.VARCHAR(length=16),
                    nullable=True)
    op.drop_column('users', 'profile_pic')