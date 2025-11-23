"""Add teams and usage billing tables

Revision ID: teams_usage_001
Revises: rag_001_add_pgvector_support
Create Date: 2024-11-23

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'teams_usage_001'
down_revision = 'rag_001_add_pgvector_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # TEAM COLLABORATION TABLES
    # ==========================================================================

    # Teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('is_public', sa.Boolean(), default=False, nullable=False),
        sa.Column('member_count', sa.Integer(), default=1, nullable=False),
        sa.Column('settings', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=datetime.utcnow, nullable=True),
    )
    op.create_index('ix_teams_owner', 'teams', ['owner_username'])

    # Team members table
    op.create_table(
        'team_members',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), default='member', nullable=False),
        sa.Column('can_invite', sa.Boolean(), default=False, nullable=False),
        sa.Column('can_edit_docs', sa.Boolean(), default=True, nullable=False),
        sa.Column('can_delete_docs', sa.Boolean(), default=False, nullable=False),
        sa.Column('can_manage_kb', sa.Boolean(), default=False, nullable=False),
        sa.Column('joined_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )
    op.create_index('ix_team_members_team', 'team_members', ['team_id'])
    op.create_index('ix_team_members_user', 'team_members', ['username'])
    op.create_unique_constraint('uq_team_member', 'team_members', ['team_id', 'username'])

    # Team invitations table
    op.create_table(
        'team_invitations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('role', sa.String(20), default='member', nullable=False),
        sa.Column('invited_by', sa.String(50), sa.ForeignKey('users.username', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_team_invitations_team', 'team_invitations', ['team_id'])
    op.create_index('ix_team_invitations_email', 'team_invitations', ['email'])

    # Team knowledge bases (sharing)
    op.create_table(
        'team_knowledge_bases',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('knowledge_base_id', sa.Integer(), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('permission', sa.String(20), default='read', nullable=False),
        sa.Column('shared_by', sa.String(50), sa.ForeignKey('users.username', ondelete='SET NULL'), nullable=True),
        sa.Column('shared_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )
    op.create_unique_constraint('uq_team_kb', 'team_knowledge_bases', ['team_id', 'knowledge_base_id'])

    # Document comments
    op.create_table(
        'document_comments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='SET NULL'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('document_comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=datetime.utcnow, nullable=True),
    )
    op.create_index('ix_document_comments_doc', 'document_comments', ['document_id'])

    # Activity logs
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=True),
        sa.Column('knowledge_base_id', sa.Integer(), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=True),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(50), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False, index=True),
    )
    op.create_index('ix_activity_logs_team', 'activity_logs', ['team_id'])
    op.create_index('ix_activity_logs_kb', 'activity_logs', ['knowledge_base_id'])

    # ==========================================================================
    # USAGE & BILLING TABLES
    # ==========================================================================

    # User subscriptions
    op.create_table(
        'user_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('plan', sa.String(20), default='free', nullable=False),
        sa.Column('status', sa.String(20), default='active', nullable=False),
        sa.Column('stripe_customer_id', sa.String(100), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(100), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), default=False, nullable=False),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=datetime.utcnow, nullable=True),
    )
    op.create_index('ix_user_subscriptions_plan', 'user_subscriptions', ['plan'])
    op.create_index('ix_user_subscriptions_status', 'user_subscriptions', ['status'])

    # Usage records
    op.create_table(
        'usage_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('user_subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('api_calls', sa.Integer(), default=0, nullable=False),
        sa.Column('documents_uploaded', sa.Integer(), default=0, nullable=False),
        sa.Column('ai_requests', sa.Integer(), default=0, nullable=False),
        sa.Column('storage_bytes', sa.BigInteger(), default=0, nullable=False),
        sa.Column('search_queries', sa.Integer(), default=0, nullable=False),
        sa.Column('build_suggestions', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )
    op.create_index('ix_usage_records_user', 'usage_records', ['username'])
    op.create_index('ix_usage_records_period', 'usage_records', ['period_start', 'period_end'])

    # Rate limit overrides
    op.create_table(
        'rate_limit_overrides',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), sa.ForeignKey('users.username', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('api_calls_per_minute', sa.Integer(), nullable=True),
        sa.Column('api_calls_per_day', sa.Integer(), nullable=True),
        sa.Column('documents_per_month', sa.Integer(), nullable=True),
        sa.Column('ai_requests_per_day', sa.Integer(), nullable=True),
        sa.Column('storage_mb', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('granted_by', sa.String(50), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('rate_limit_overrides')
    op.drop_table('usage_records')
    op.drop_table('user_subscriptions')
    op.drop_table('activity_logs')
    op.drop_table('document_comments')
    op.drop_table('team_knowledge_bases')
    op.drop_table('team_invitations')
    op.drop_table('team_members')
    op.drop_table('teams')
