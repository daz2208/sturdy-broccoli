"""Make document_id nullable for combined ideas

Revision ID: combined_ideas_001
Revises: kb_settings_001
Create Date: 2025-12-07
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'combined_ideas_001'
down_revision = 'kb_settings_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make document_id nullable so combined ideas (spanning multiple docs) can be stored
    op.alter_column('build_idea_seeds', 'document_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    # Delete combined ideas (document_id IS NULL) before making column non-nullable
    op.execute("DELETE FROM build_idea_seeds WHERE document_id IS NULL")
    op.alter_column('build_idea_seeds', 'document_id',
                    existing_type=sa.Integer(),
                    nullable=False)
