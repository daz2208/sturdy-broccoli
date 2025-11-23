"""Add pgvector support for enhanced RAG

Revision ID: rag_001
Revises: hier_001
Create Date: 2025-11-23

Adds:
- pgvector extension for native vector operations
- embedding_vector column with proper vector type
- parent_chunk_id for parent-child chunking
- chunk_type for distinguishing parent/child chunks
- IVFFlat index for fast similarity search
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'rag_001'
down_revision = 'hier_001'
branch_labels = None
depends_on = None


def upgrade():
    # Get connection for raw SQL (needed for pgvector extension)
    connection = op.get_bind()

    # 1. Enable pgvector extension (PostgreSQL only)
    # This will fail silently on SQLite
    try:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("pgvector extension enabled successfully")
    except Exception as e:
        print(f"Note: pgvector extension not available (SQLite?): {e}")

    # 2. Add parent_chunk_id column for parent-child relationships
    op.add_column('document_chunks',
        sa.Column('parent_chunk_id', sa.Integer(), nullable=True)
    )

    # 3. Add chunk_type column (parent vs child)
    op.add_column('document_chunks',
        sa.Column('chunk_type', sa.String(20), server_default='child', nullable=False)
    )

    # 4. Add foreign key for parent_chunk_id
    op.create_foreign_key(
        'fk_chunk_parent',
        'document_chunks',
        'document_chunks',
        ['parent_chunk_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 5. Create index for parent-child lookups
    op.create_index('idx_chunks_parent', 'document_chunks', ['parent_chunk_id'])

    # 6. Create index for chunk type filtering
    op.create_index('idx_chunks_type', 'document_chunks', ['chunk_type'])

    # 7. Add vector column if PostgreSQL with pgvector
    # We use raw SQL because SQLAlchemy doesn't have native vector type
    try:
        connection.execute(text("""
            ALTER TABLE document_chunks
            ADD COLUMN IF NOT EXISTS embedding_vector vector(1536)
        """))
        print("Added embedding_vector column (vector(1536))")

        # 8. Create IVFFlat index for fast similarity search
        # IVFFlat is good for datasets with 1k-1M vectors
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
            ON document_chunks
            USING ivfflat (embedding_vector vector_cosine_ops)
            WITH (lists = 100)
        """))
        print("Created IVFFlat index for vector similarity search")

    except Exception as e:
        print(f"Note: Could not add pgvector columns (SQLite?): {e}")
        print("Falling back to JSON embedding storage")


def downgrade():
    connection = op.get_bind()

    # Drop pgvector index and column (PostgreSQL only)
    try:
        connection.execute(text("DROP INDEX IF EXISTS idx_chunks_embedding_ivfflat"))
        connection.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_vector"))
    except Exception:
        pass

    # Drop indexes
    op.drop_index('idx_chunks_type', table_name='document_chunks')
    op.drop_index('idx_chunks_parent', table_name='document_chunks')

    # Drop foreign key
    op.drop_constraint('fk_chunk_parent', 'document_chunks', type_='foreignkey')

    # Drop columns
    op.drop_column('document_chunks', 'chunk_type')
    op.drop_column('document_chunks', 'parent_chunk_id')
