"""Add hierarchical summarization tables

Revision ID: hier_001
Revises: kb001_knowledge_bases
Create Date: 2025-11-21

Adds tables for:
- document_chunks: Store document chunks with embeddings
- document_summaries: Store hierarchical summaries (chunk/section/doc level)
- build_idea_seeds: Store pre-computed build suggestions per document
- Adds processing status columns to documents table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'hier_001'
down_revision = 'kb001_knowledge_bases'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('knowledge_base_id', sa.String(36), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('start_token', sa.Integer(), nullable=False),
        sa.Column('end_token', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),  # Store as JSON for SQLite compatibility
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('concepts', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE')
    )
    op.create_index('idx_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('idx_chunks_kb_id', 'document_chunks', ['knowledge_base_id'])
    op.create_index('idx_chunks_doc_index', 'document_chunks', ['document_id', 'chunk_index'])

    # 2. Create document_summaries table
    op.create_table(
        'document_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('knowledge_base_id', sa.String(36), nullable=False),
        sa.Column('summary_type', sa.String(50), nullable=False),  # 'chunk', 'section', 'document'
        sa.Column('summary_level', sa.Integer(), nullable=False),  # 1=chunk, 2=section, 3=document
        sa.Column('parent_id', sa.Integer(), nullable=True),  # Reference to parent summary
        sa.Column('chunk_id', sa.Integer(), nullable=True),  # Reference to source chunk (for chunk summaries)
        sa.Column('short_summary', sa.Text(), nullable=False),  # 100-200 tokens
        sa.Column('long_summary', sa.Text(), nullable=True),  # 500-1000 tokens
        sa.Column('key_concepts', sa.JSON(), nullable=True),
        sa.Column('tech_stack', sa.JSON(), nullable=True),
        sa.Column('skill_profile', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['document_summaries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='SET NULL')
    )
    op.create_index('idx_summaries_document_id', 'document_summaries', ['document_id'])
    op.create_index('idx_summaries_kb_id', 'document_summaries', ['knowledge_base_id'])
    op.create_index('idx_summaries_type', 'document_summaries', ['summary_type'])
    op.create_index('idx_summaries_level', 'document_summaries', ['summary_level'])

    # 3. Create build_idea_seeds table
    op.create_table(
        'build_idea_seeds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('knowledge_base_id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(50), nullable=False),  # 'beginner', 'intermediate', 'advanced'
        sa.Column('dependencies', sa.JSON(), nullable=True),  # Other concepts/docs needed
        sa.Column('referenced_sections', sa.JSON(), nullable=True),  # Which doc sections support this
        sa.Column('feasibility', sa.String(50), nullable=True),  # 'high', 'medium', 'low'
        sa.Column('effort_estimate', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE')
    )
    op.create_index('idx_build_ideas_document_id', 'build_idea_seeds', ['document_id'])
    op.create_index('idx_build_ideas_kb_id', 'build_idea_seeds', ['knowledge_base_id'])
    op.create_index('idx_build_ideas_difficulty', 'build_idea_seeds', ['difficulty'])

    # 4. Add processing status columns to documents table
    op.add_column('documents', sa.Column('chunking_status', sa.String(50), server_default='pending', nullable=False))
    op.add_column('documents', sa.Column('summary_status', sa.String(50), server_default='pending', nullable=False))
    op.add_column('documents', sa.Column('chunk_count', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    # Remove columns from documents table
    op.drop_column('documents', 'chunk_count')
    op.drop_column('documents', 'summary_status')
    op.drop_column('documents', 'chunking_status')

    # Drop build_idea_seeds table
    op.drop_index('idx_build_ideas_difficulty', table_name='build_idea_seeds')
    op.drop_index('idx_build_ideas_kb_id', table_name='build_idea_seeds')
    op.drop_index('idx_build_ideas_document_id', table_name='build_idea_seeds')
    op.drop_table('build_idea_seeds')

    # Drop document_summaries table
    op.drop_index('idx_summaries_level', table_name='document_summaries')
    op.drop_index('idx_summaries_type', table_name='document_summaries')
    op.drop_index('idx_summaries_kb_id', table_name='document_summaries')
    op.drop_index('idx_summaries_document_id', table_name='document_summaries')
    op.drop_table('document_summaries')

    # Drop document_chunks table
    op.drop_index('idx_chunks_doc_index', table_name='document_chunks')
    op.drop_index('idx_chunks_kb_id', table_name='document_chunks')
    op.drop_index('idx_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
