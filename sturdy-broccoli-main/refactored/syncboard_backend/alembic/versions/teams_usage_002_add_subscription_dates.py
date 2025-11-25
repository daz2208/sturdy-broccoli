"""Add subscription date columns to user_subscriptions

Revision ID: teams_usage_002
Revises: agentic_001
Create Date: 2025-11-25

Adds missing date columns to user_subscriptions:
- started_at (when subscription started)
- expires_at (when subscription expires)
- cancelled_at (when subscription was cancelled)
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'teams_usage_002'
down_revision = 'agentic_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add started_at column (required, default to created_at or now)
    op.add_column('user_subscriptions',
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # Remove server_default after creation (we only need it for existing rows)
    op.alter_column('user_subscriptions', 'started_at', server_default=None)

    # Add expires_at column (optional, for paid subscriptions)
    op.add_column('user_subscriptions',
        sa.Column('expires_at', sa.DateTime(), nullable=True)
    )

    # Add cancelled_at column (optional, when user cancels)
    op.add_column('user_subscriptions',
        sa.Column('cancelled_at', sa.DateTime(), nullable=True)
    )

    # Copy created_at to started_at for existing subscriptions
    op.execute("""
        UPDATE user_subscriptions
        SET started_at = created_at
        WHERE started_at IS NULL OR started_at > created_at
    """)


def downgrade():
    op.drop_column('user_subscriptions', 'cancelled_at')
    op.drop_column('user_subscriptions', 'expires_at')
    op.drop_column('user_subscriptions', 'started_at')
