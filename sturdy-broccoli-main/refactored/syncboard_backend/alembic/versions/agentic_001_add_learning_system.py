"""Add agentic learning system tables

Revision ID: agentic_001
Revises: teams_usage_001
Create Date: 2025-11-24

Adds tables for self-learning AI system:
- ai_decisions: Track all AI decisions with confidence scores
- user_feedback: Track user corrections to learn from mistakes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'agentic_001'
down_revision = 'teams_usage_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create ai_decisions table
    op.create_table('ai_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_type', sa.String(length=50), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('knowledge_base_id', sa.String(length=36), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('output_data', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('validated', sa.Boolean(), nullable=False),
        sa.Column('validation_result', sa.String(length=20), nullable=True),
        sa.Column('validation_timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.doc_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['username'], ['users.username'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_decision_created', 'ai_decisions', ['created_at'], unique=False)
    op.create_index('idx_ai_decision_type_confidence', 'ai_decisions', ['decision_type', 'confidence_score'], unique=False)
    op.create_index('idx_ai_decision_user_type', 'ai_decisions', ['username', 'decision_type'], unique=False)
    op.create_index('idx_ai_decision_validation', 'ai_decisions', ['validated', 'confidence_score'], unique=False)
    op.create_index(op.f('ix_ai_decisions_cluster_id'), 'ai_decisions', ['cluster_id'], unique=False)
    op.create_index(op.f('ix_ai_decisions_confidence_score'), 'ai_decisions', ['confidence_score'], unique=False)
    op.create_index(op.f('ix_ai_decisions_decision_type'), 'ai_decisions', ['decision_type'], unique=False)
    op.create_index(op.f('ix_ai_decisions_document_id'), 'ai_decisions', ['document_id'], unique=False)
    op.create_index(op.f('ix_ai_decisions_knowledge_base_id'), 'ai_decisions', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_ai_decisions_username'), 'ai_decisions', ['username'], unique=False)
    op.create_index(op.f('ix_ai_decisions_validated'), 'ai_decisions', ['validated'], unique=False)

    # Create user_feedback table
    op.create_table('user_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('feedback_type', sa.String(length=50), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('knowledge_base_id', sa.String(length=36), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('ai_decision_id', sa.Integer(), nullable=True),
        sa.Column('original_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('user_reasoning', sa.Text(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('improvement_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ai_decision_id'], ['ai_decisions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.doc_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['username'], ['users.username'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_feedback_document', 'user_feedback', ['document_id'], unique=False)
    op.create_index('idx_feedback_processed', 'user_feedback', ['processed', 'created_at'], unique=False)
    op.create_index('idx_feedback_type_user', 'user_feedback', ['feedback_type', 'username'], unique=False)
    op.create_index('idx_feedback_user_kb', 'user_feedback', ['username', 'knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_user_feedback_feedback_type'), 'user_feedback', ['feedback_type'], unique=False)
    op.create_index(op.f('ix_user_feedback_knowledge_base_id'), 'user_feedback', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_user_feedback_processed'), 'user_feedback', ['processed'], unique=False)
    op.create_index(op.f('ix_user_feedback_username'), 'user_feedback', ['username'], unique=False)


def downgrade():
    # Drop user_feedback table
    op.drop_index(op.f('ix_user_feedback_username'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_processed'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_knowledge_base_id'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_feedback_type'), table_name='user_feedback')
    op.drop_index('idx_feedback_user_kb', table_name='user_feedback')
    op.drop_index('idx_feedback_type_user', table_name='user_feedback')
    op.drop_index('idx_feedback_processed', table_name='user_feedback')
    op.drop_index('idx_feedback_document', table_name='user_feedback')
    op.drop_table('user_feedback')

    # Drop ai_decisions table
    op.drop_index(op.f('ix_ai_decisions_validated'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_username'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_knowledge_base_id'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_document_id'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_decision_type'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_confidence_score'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_cluster_id'), table_name='ai_decisions')
    op.drop_index('idx_ai_decision_validation', table_name='ai_decisions')
    op.drop_index('idx_ai_decision_user_type', table_name='ai_decisions')
    op.drop_index('idx_ai_decision_type_confidence', table_name='ai_decisions')
    op.drop_index('idx_ai_decision_created', table_name='ai_decisions')
    op.drop_table('ai_decisions')
