"""Add saved_ideas table for bookmarking build ideas

Revision ID: saved_ideas_001
Revises: teams_usage_002
Create Date: 2025-11-30

Adds table for:
- saved_ideas: User-saved build ideas with progress tracking
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'saved_ideas_001'
down_revision = 'teams_usage_002'
branch_labels = None
depends_on = None


def upgrade():
    # Create saved_ideas table
    op.create_table(
        'saved_ideas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('idea_seed_id', sa.Integer(), nullable=True),
        sa.Column('custom_title', sa.String(500), nullable=True),
        sa.Column('custom_description', sa.Text(), nullable=True),
        sa.Column('custom_data', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='saved'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create foreign key constraints
    op.create_foreign_key(
        'fk_saved_ideas_user',
        'saved_ideas', 'users',
        ['user_id'], ['username'],
        ondelete='CASCADE'
    )

    op.create_foreign_key(
        'fk_saved_ideas_seed',
        'saved_ideas', 'build_idea_seeds',
        ['idea_seed_id'], ['id'],
        ondelete='CASCADE'
    )

    # Create indexes
    op.create_index('ix_saved_ideas_user_id', 'saved_ideas', ['user_id'])
    op.create_index('ix_saved_ideas_user_status', 'saved_ideas', ['user_id', 'status'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_saved_ideas_user_status', table_name='saved_ideas')
    op.drop_index('ix_saved_ideas_user_id', table_name='saved_ideas')

    # Drop foreign keys
    op.drop_constraint('fk_saved_ideas_seed', 'saved_ideas', type_='foreignkey')
    op.drop_constraint('fk_saved_ideas_user', 'saved_ideas', type_='foreignkey')

    # Drop table
    op.drop_table('saved_ideas')
