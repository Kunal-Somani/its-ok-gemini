"""Create tasks table

Revision ID: 5d002283d7e0
Revises: 
Create Date: 2026-04-27 23:37:56.214466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d002283d7e0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tasks',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('QUEUED', 'ANALYZING', 'GENERATING', 'DEPLOYING', 'SUCCESS', 'FAILED', name='taskstatus'), nullable=False, server_default='QUEUED'),
        sa.Column('task_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('round_index', sa.Integer(), nullable=False),
        sa.Column('nonce', sa.String(), nullable=False),
        sa.Column('llm_metadata', sa.JSON(), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nonce')
    )
    op.create_index(op.f('ix_tasks_created_at'), 'tasks', ['created_at'], unique=False)
    op.create_index(op.f('ix_tasks_task_name'), 'tasks', ['task_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_task_name'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_created_at'), table_name='tasks')
    op.drop_table('tasks')
    op.execute('DROP TYPE taskstatus')
