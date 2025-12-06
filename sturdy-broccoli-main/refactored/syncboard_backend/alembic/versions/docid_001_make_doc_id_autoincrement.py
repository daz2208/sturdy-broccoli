"""make doc_id auto-increment with sequence

Revision ID: docid_001
Revises: teams_usage_002
Create Date: 2025-12-06

Fixes race condition where concurrent workers assign duplicate doc_ids.
Database-level SERIAL ensures atomic, unique ID generation.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'docid_001'
down_revision = 'teams_usage_002'  # Latest migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Convert doc_id to auto-incrementing SERIAL.

    Creates a sequence and sets it as default for doc_id column.
    Ensures concurrent workers get unique IDs from database.
    """
    # Create sequence for doc_id (if not exists)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'documents_doc_id_seq') THEN
                CREATE SEQUENCE documents_doc_id_seq;
            END IF;
        END
        $$;
    """)

    # Set sequence to current MAX(doc_id) + 1 to avoid conflicts
    op.execute("""
        SELECT setval('documents_doc_id_seq', COALESCE((SELECT MAX(doc_id) FROM documents), 0) + 1, false);
    """)

    # Set doc_id column to use sequence as default
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN doc_id SET DEFAULT nextval('documents_doc_id_seq');
    """)

    # Same for document_vectors table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'document_vectors_doc_id_seq') THEN
                CREATE SEQUENCE document_vectors_doc_id_seq;
            END IF;
        END
        $$;
    """)

    op.execute("""
        SELECT setval('document_vectors_doc_id_seq', COALESCE((SELECT MAX(doc_id) FROM document_vectors), 0) + 1, false);
    """)

    op.execute("""
        ALTER TABLE document_vectors
        ALTER COLUMN doc_id SET DEFAULT nextval('document_vectors_doc_id_seq');
    """)


def downgrade():
    """
    Rollback: Remove sequence defaults from doc_id columns.

    Reverts to manual doc_id assignment (pre-fix behavior).
    """
    # Remove default from documents table
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN doc_id DROP DEFAULT;
    """)

    # Remove default from document_vectors table
    op.execute("""
        ALTER TABLE document_vectors
        ALTER COLUMN doc_id DROP DEFAULT;
    """)

    # Optionally drop sequences (commented out to preserve data)
    # op.execute("DROP SEQUENCE IF EXISTS documents_doc_id_seq;")
    # op.execute("DROP SEQUENCE IF EXISTS document_vectors_doc_id_seq;")
