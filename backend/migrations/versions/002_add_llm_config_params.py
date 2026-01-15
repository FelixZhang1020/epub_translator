"""Add max_tokens and other parameters to llm_configurations table.

Revision ID: 002
Revises: 001
Create Date: 2025-01-13

This migration adds the following columns to llm_configurations:
- max_tokens: Maximum output tokens for LLM calls
- top_p: Top-p sampling parameter
- frequency_penalty: Frequency penalty for repetition
- presence_penalty: Presence penalty for topic diversity
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_llm_config_params'
down_revision = '001_content_classification'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add LLM configuration parameters."""
    # Add max_tokens column
    op.add_column(
        'llm_configurations',
        sa.Column('max_tokens', sa.Integer(), nullable=True, default=4096)
    )

    # Add top_p column
    op.add_column(
        'llm_configurations',
        sa.Column('top_p', sa.Float(), nullable=True)
    )

    # Add frequency_penalty column
    op.add_column(
        'llm_configurations',
        sa.Column('frequency_penalty', sa.Float(), nullable=True)
    )

    # Add presence_penalty column
    op.add_column(
        'llm_configurations',
        sa.Column('presence_penalty', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    """Remove LLM configuration parameters."""
    op.drop_column('llm_configurations', 'presence_penalty')
    op.drop_column('llm_configurations', 'frequency_penalty')
    op.drop_column('llm_configurations', 'top_p')
    op.drop_column('llm_configurations', 'max_tokens')

