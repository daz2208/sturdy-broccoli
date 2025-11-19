"""Add knowledge bases and build suggestions tables

Revision ID: kb001_knowledge_bases
Revises: 433d6fa5c900
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'kb001_knowledge_bases'
down_revision = '433d6fa5c900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create knowledge_bases table first (referenced by other tables)
    op.create_table(
        'knowledge_bases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('owner_username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('is_default', sa.Boolean, default=False, nullable=False, index=True),
        sa.Column('document_count', sa.Integer, default=0, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_accessed_at', sa.DateTime, nullable=True),
    )
    op.create_index('idx_kb_owner_name', 'knowledge_bases', ['owner_username', 'name'])

    # Create build_suggestions table
    op.create_table(
        'build_suggestions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('knowledge_base_id', sa.String(36), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('feasibility', sa.String(20), nullable=False),
        sa.Column('effort_estimate', sa.String(100), nullable=True),
        sa.Column('required_skills', sa.JSON, nullable=True),
        sa.Column('missing_knowledge', sa.JSON, nullable=True),
        sa.Column('relevant_clusters', sa.JSON, nullable=True),
        sa.Column('starter_steps', sa.JSON, nullable=True),
        sa.Column('file_structure', sa.Text, nullable=True),
        sa.Column('knowledge_coverage', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('is_completed', sa.Boolean, default=False, nullable=False, index=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )
    op.create_index('idx_suggestion_kb_created', 'build_suggestions', ['knowledge_base_id', 'created_at'])
    op.create_index('idx_suggestion_feasibility', 'build_suggestions', ['feasibility'])

    # Add knowledge_base_id to existing tables
    op.add_column('documents', sa.Column('knowledge_base_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_documents_knowledge_base',
        'documents', 'knowledge_bases',
        ['knowledge_base_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_doc_kb', 'documents', ['knowledge_base_id'])

    op.add_column('clusters', sa.Column('knowledge_base_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_clusters_knowledge_base',
        'clusters', 'knowledge_bases',
        ['knowledge_base_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_cluster_kb', 'clusters', ['knowledge_base_id'])

    # Create default knowledge base for each existing user
    # and migrate their documents to it
    conn = op.get_bind()

    # Get all users
    users = conn.execute(sa.text("SELECT username FROM users")).fetchall()

    for (username,) in users:
        # Create default KB for user
        kb_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                INSERT INTO knowledge_bases (id, name, description, owner_username, is_default, document_count, created_at, updated_at)
                VALUES (:id, :name, :desc, :owner, :is_default, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                'id': kb_id,
                'name': 'Main Knowledge Base',
                'desc': 'Default knowledge base for all your documents',
                'owner': username,
                'is_default': True
            }
        )

        # Migrate user's documents to their default KB
        conn.execute(
            sa.text("""
                UPDATE documents
                SET knowledge_base_id = :kb_id
                WHERE owner_username = :owner
            """),
            {'kb_id': kb_id, 'owner': username}
        )

        # Migrate user's clusters to their default KB
        # Note: Clusters don't have owner_username, so we need to infer from documents
        conn.execute(
            sa.text("""
                UPDATE clusters
                SET knowledge_base_id = :kb_id
                WHERE id IN (
                    SELECT DISTINCT cluster_id
                    FROM documents
                    WHERE owner_username = :owner AND cluster_id IS NOT NULL
                )
            """),
            {'kb_id': kb_id, 'owner': username}
        )

        # Update document count
        doc_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM documents WHERE knowledge_base_id = :kb_id"),
            {'kb_id': kb_id}
        ).scalar()

        conn.execute(
            sa.text("UPDATE knowledge_bases SET document_count = :count WHERE id = :kb_id"),
            {'count': doc_count, 'kb_id': kb_id}
        )


def downgrade() -> None:
    # Remove foreign keys first
    op.drop_constraint('fk_documents_knowledge_base', 'documents', type_='foreignkey')
    op.drop_constraint('fk_clusters_knowledge_base', 'clusters', type_='foreignkey')

    # Remove indexes
    op.drop_index('idx_doc_kb', 'documents')
    op.drop_index('idx_cluster_kb', 'clusters')

    # Remove columns
    op.drop_column('documents', 'knowledge_base_id')
    op.drop_column('clusters', 'knowledge_base_id')

    # Drop tables
    op.drop_table('build_suggestions')
    op.drop_table('knowledge_bases')
