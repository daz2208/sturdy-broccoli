"""Add settings column to knowledge_bases

Revision ID: kb_settings_001
Revises: teams_usage_001
Create Date: 2025-11-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'kb_settings_001'
down_revision = 'teams_usage_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add settings JSON column with default empty object
    op.add_column('knowledge_bases', sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    # Backfill existing rows with empty dict to avoid null issues in code
    op.execute("UPDATE knowledge_bases SET settings = '{}'::json WHERE settings IS NULL")


def downgrade() -> None:
    op.drop_column('knowledge_bases', 'settings')
