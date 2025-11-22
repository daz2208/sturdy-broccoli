"""SyncBoard 3.0 Enhancements - Phase 10

Creates tables for:
- project_goals: User project goals and constraints
- project_attempts: Track project attempts and learnings
- generated_code: Store generated code files
- n8n_workflows: Store generated n8n workflows
- market_validations: Store market validation results

Also adds columns to documents table:
- document_tags: JSON field for document categorization
- related_project_id: Foreign key to project_attempts

Revision ID: phase10_001
Revises: hier_001_add_hierarchical_summarization
Create Date: 2025-01-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase10_001'
down_revision = 'hier_001_add_hierarchical_summarization'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # Create project_goals table
    # ==========================================================================
    op.create_table(
        'project_goals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(255), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_type', sa.String(50), nullable=False),
        sa.Column('priority', sa.Integer(), default=0, nullable=False),
        sa.Column('constraints', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for project_goals
    op.create_index('idx_project_goals_user', 'project_goals', ['user_id'])
    op.create_index('idx_project_goals_type', 'project_goals', ['goal_type'])
    op.create_index('idx_project_goals_priority', 'project_goals', ['user_id', 'priority'])

    # ==========================================================================
    # Create project_attempts table
    # ==========================================================================
    op.create_table(
        'project_attempts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(255), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_id', sa.String(255), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='planned'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('abandoned_at', sa.DateTime(), nullable=True),
        sa.Column('repository_url', sa.String(500), nullable=True),
        sa.Column('demo_url', sa.String(500), nullable=True),
        sa.Column('learnings', sa.Text(), nullable=True),
        sa.Column('difficulty_rating', sa.Integer(), nullable=True),
        sa.Column('time_spent_hours', sa.Integer(), nullable=True),
        sa.Column('revenue_generated', sa.Float(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for project_attempts
    op.create_index('idx_project_attempts_user', 'project_attempts', ['user_id'])
    op.create_index('idx_project_attempts_status', 'project_attempts', ['status'])
    op.create_index('idx_project_attempts_user_status', 'project_attempts', ['user_id', 'status'])
    op.create_index('idx_project_attempts_created', 'project_attempts', ['created_at'])

    # ==========================================================================
    # Create generated_code table
    # ==========================================================================
    op.create_table(
        'generated_code',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(255), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('project_attempt_id', sa.Integer(), sa.ForeignKey('project_attempts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('generation_type', sa.String(50), nullable=False),
        sa.Column('language', sa.String(50), nullable=True),
        sa.Column('filename', sa.String(255), nullable=True),
        sa.Column('code_content', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('setup_instructions', sa.Text(), nullable=True),
        sa.Column('prompt_used', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for generated_code
    op.create_index('idx_generated_code_user', 'generated_code', ['user_id'])
    op.create_index('idx_generated_code_project', 'generated_code', ['project_attempt_id'])
    op.create_index('idx_generated_code_type', 'generated_code', ['generation_type'])

    # ==========================================================================
    # Create n8n_workflows table
    # ==========================================================================
    op.create_table(
        'n8n_workflows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(255), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('workflow_json', sa.JSON(), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('required_integrations', sa.JSON(), nullable=True),
        sa.Column('trigger_type', sa.String(100), nullable=True),
        sa.Column('estimated_complexity', sa.String(50), nullable=True),
        sa.Column('tested', sa.Boolean(), default=False, nullable=False),
        sa.Column('deployed', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for n8n_workflows
    op.create_index('idx_n8n_workflows_user', 'n8n_workflows', ['user_id'])
    op.create_index('idx_n8n_workflows_trigger', 'n8n_workflows', ['trigger_type'])
    op.create_index('idx_n8n_workflows_complexity', 'n8n_workflows', ['estimated_complexity'])

    # ==========================================================================
    # Create market_validations table
    # ==========================================================================
    op.create_table(
        'market_validations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_attempt_id', sa.Integer(), sa.ForeignKey('project_attempts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.String(255), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('validation_date', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('market_size_estimate', sa.String(100), nullable=True),
        sa.Column('competition_level', sa.String(100), nullable=True),
        sa.Column('competitors', sa.JSON(), nullable=True),
        sa.Column('unique_advantage', sa.Text(), nullable=True),
        sa.Column('potential_revenue_estimate', sa.String(100), nullable=True),
        sa.Column('validation_sources', sa.JSON(), nullable=True),
        sa.Column('recommendation', sa.String(50), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('full_analysis', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for market_validations
    op.create_index('idx_market_validations_project', 'market_validations', ['project_attempt_id'])
    op.create_index('idx_market_validations_user', 'market_validations', ['user_id'])
    op.create_index('idx_market_validations_recommendation', 'market_validations', ['recommendation'])

    # ==========================================================================
    # Add new columns to documents table
    # ==========================================================================
    op.add_column('documents', sa.Column('document_tags', sa.JSON(), nullable=True))
    op.add_column('documents', sa.Column('related_project_id', sa.Integer(),
                                          sa.ForeignKey('project_attempts.id', ondelete='SET NULL'),
                                          nullable=True))
    op.create_index('idx_documents_related_project', 'documents', ['related_project_id'])


def downgrade():
    # Drop indexes on documents
    op.drop_index('idx_documents_related_project', 'documents')

    # Drop columns from documents
    op.drop_column('documents', 'related_project_id')
    op.drop_column('documents', 'document_tags')

    # Drop indexes
    op.drop_index('idx_market_validations_recommendation', 'market_validations')
    op.drop_index('idx_market_validations_user', 'market_validations')
    op.drop_index('idx_market_validations_project', 'market_validations')

    op.drop_index('idx_n8n_workflows_complexity', 'n8n_workflows')
    op.drop_index('idx_n8n_workflows_trigger', 'n8n_workflows')
    op.drop_index('idx_n8n_workflows_user', 'n8n_workflows')

    op.drop_index('idx_generated_code_type', 'generated_code')
    op.drop_index('idx_generated_code_project', 'generated_code')
    op.drop_index('idx_generated_code_user', 'generated_code')

    op.drop_index('idx_project_attempts_created', 'project_attempts')
    op.drop_index('idx_project_attempts_user_status', 'project_attempts')
    op.drop_index('idx_project_attempts_status', 'project_attempts')
    op.drop_index('idx_project_attempts_user', 'project_attempts')

    op.drop_index('idx_project_goals_priority', 'project_goals')
    op.drop_index('idx_project_goals_type', 'project_goals')
    op.drop_index('idx_project_goals_user', 'project_goals')

    # Drop tables in reverse order of creation (due to foreign keys)
    op.drop_table('market_validations')
    op.drop_table('n8n_workflows')
    op.drop_table('generated_code')
    op.drop_table('project_attempts')
    op.drop_table('project_goals')
