"""Add source_zip_filename to documents for parent ZIP tracking

Revision ID: zip_tracking_001
Revises: saved_ideas_001
Create Date: 2025-12-07

Adds column to track which ZIP archive a document was extracted from.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'zip_tracking_001'
down_revision = 'saved_ideas_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source_zip_filename column to documents table
    op.add_column('documents', sa.Column('source_zip_filename', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'source_zip_filename')
