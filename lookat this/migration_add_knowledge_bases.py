"""Add knowledge base architecture with build suggestions storage

Revision ID: kb001_knowledge_bases
Revises: 433d6fa5c900
Create Date: 2025-11-19

Changes:
- Add knowledge_bases table
- Add knowledge_base_id to documents table
- Add build_suggestions table for saving generated suggestions
- Create default knowledge base and migrate existing documents
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


def upgrade():
    """Add knowledge base tables and columns."""
    
    # 1. Create knowledge_bases table
    op.create_table(
        'knowledge_bases',
        sa.Column('id', sa.String(36), primary_key=True),  # UUID as string
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('owner_username', sa.String(50), sa.ForeignKey('users.username'), nullable=False, index=True),
        sa.Column('is_default', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()'), onupdate=sa.text('NOW()'), nullable=False),
        sa.Column('document_count', sa.Integer, default=0, nullable=False),
        sa.Column('last_accessed_at', sa.DateTime, nullable=True),
    )
    
    # Add indexes
    op.create_index('idx_kb_owner', 'knowledge_bases', ['owner_username'])
    op.create_index('idx_kb_name', 'knowledge_bases', ['name'])
    op.create_index('idx_kb_is_default', 'knowledge_bases', ['is_default'])
    
    # 2. Add knowledge_base_id to documents table
    op.add_column('documents', sa.Column('knowledge_base_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_document_knowledge_base',
        'documents', 'knowledge_bases',
        ['knowledge_base_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_doc_knowledge_base', 'documents', ['knowledge_base_id'])
    
    # 3. Add knowledge_base_id to clusters table  
    op.add_column('clusters', sa.Column('knowledge_base_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_cluster_knowledge_base',
        'clusters', 'knowledge_bases',
        ['knowledge_base_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_cluster_knowledge_base', 'clusters', ['knowledge_base_id'])
    
    # 4. Create build_suggestions table
    op.create_table(
        'build_suggestions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('knowledge_base_id', sa.String(36), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('feasibility', sa.String(20), nullable=False),  # high, medium, low
        sa.Column('effort_estimate', sa.String(100), nullable=True),
        sa.Column('required_skills', postgresql.JSON, nullable=True),  # Array of strings
        sa.Column('missing_knowledge', postgresql.JSON, nullable=True),  # Array of strings
        sa.Column('relevant_clusters', postgresql.JSON, nullable=True),  # Array of cluster IDs
        sa.Column('starter_steps', postgresql.JSON, nullable=True),  # Array of strings
        sa.Column('file_structure', sa.Text, nullable=True),
        sa.Column('knowledge_coverage', sa.String(20), nullable=True),  # high, medium, low
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False, index=True),
        sa.Column('is_completed', sa.Boolean, default=False, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )
    
    # Add indexes for common queries
    op.create_index('idx_suggestion_kb_created', 'build_suggestions', ['knowledge_base_id', 'created_at'])
    op.create_index('idx_suggestion_feasibility', 'build_suggestions', ['feasibility'])
    op.create_index('idx_suggestion_completed', 'build_suggestions', ['is_completed'])
    
    # 5. Create default knowledge base for each user and migrate their documents
    # This requires a data migration - we'll use raw SQL
    connection = op.get_bind()
    
    # Get all users
    users = connection.execute(sa.text("SELECT username FROM users")).fetchall()
    
    for user in users:
        username = user[0]
        
        # Create default knowledge base for this user
        kb_id = str(uuid.uuid4())
        connection.execute(
            sa.text("""
                INSERT INTO knowledge_bases 
                (id, name, description, owner_username, is_default, created_at, updated_at, document_count)
                VALUES (:id, :name, :description, :owner, true, NOW(), NOW(), 0)
            """),
            {
                'id': kb_id,
                'name': 'Main Knowledge Base',
                'description': 'Your default knowledge base',
                'owner': username
            }
        )
        
        # Update all documents for this user to use the default KB
        connection.execute(
            sa.text("""
                UPDATE documents 
                SET knowledge_base_id = :kb_id 
                WHERE owner_username = :owner
            """),
            {'kb_id': kb_id, 'owner': username}
        )
        
        # Update all clusters for this user to use the default KB
        connection.execute(
            sa.text("""
                UPDATE clusters 
                SET knowledge_base_id = :kb_id
                WHERE id IN (
                    SELECT DISTINCT cluster_id 
                    FROM documents 
                    WHERE owner_username = :owner
                )
            """),
            {'kb_id': kb_id, 'owner': username}
        )
        
        # Update document count
        doc_count = connection.execute(
            sa.text("""
                SELECT COUNT(*) FROM documents 
                WHERE knowledge_base_id = :kb_id
            """),
            {'kb_id': kb_id}
        ).scalar()
        
        connection.execute(
            sa.text("""
                UPDATE knowledge_bases 
                SET document_count = :count 
                WHERE id = :kb_id
            """),
            {'count': doc_count, 'kb_id': kb_id}
        )
    
    # 6. Now make knowledge_base_id NOT NULL (after migration)
    op.alter_column('documents', 'knowledge_base_id', nullable=False)
    op.alter_column('clusters', 'knowledge_base_id', nullable=False)


def downgrade():
    """Remove knowledge base architecture."""
    
    # Drop build_suggestions table
    op.drop_table('build_suggestions')
    
    # Remove knowledge_base_id from clusters
    op.drop_constraint('fk_cluster_knowledge_base', 'clusters', type_='foreignkey')
    op.drop_index('idx_cluster_knowledge_base', 'clusters')
    op.drop_column('clusters', 'knowledge_base_id')
    
    # Remove knowledge_base_id from documents
    op.drop_constraint('fk_document_knowledge_base', 'documents', type_='foreignkey')
    op.drop_index('idx_doc_knowledge_base', 'documents')
    op.drop_column('documents', 'knowledge_base_id')
    
    # Drop knowledge_bases table
    op.drop_index('idx_kb_is_default', 'knowledge_bases')
    op.drop_index('idx_kb_name', 'knowledge_bases')
    op.drop_index('idx_kb_owner', 'knowledge_bases')
    op.drop_table('knowledge_bases')
