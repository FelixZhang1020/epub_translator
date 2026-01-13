"""Add content classification fields for proofreading filtering.

Revision ID: 001_content_classification
Revises: None
Create Date: 2025-01-13

Adds chapter_type and is_proofreadable to chapters table.
Adds content_type and is_proofreadable to paragraphs table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_content_classification"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content classification columns."""
    # Add chapter_type to chapters table
    op.add_column(
        "chapters",
        sa.Column("chapter_type", sa.String(20), server_default="main_content"),
    )
    op.add_column(
        "chapters",
        sa.Column("is_proofreadable", sa.Boolean(), server_default="1"),
    )

    # Add content_type to paragraphs table
    op.add_column(
        "paragraphs",
        sa.Column("content_type", sa.String(20), server_default="main"),
    )
    op.add_column(
        "paragraphs",
        sa.Column("is_proofreadable", sa.Boolean(), server_default="1"),
    )

    # Add indexes for efficient filtering
    op.create_index(
        "ix_chapters_chapter_type", "chapters", ["chapter_type"]
    )
    op.create_index(
        "ix_chapters_is_proofreadable", "chapters", ["is_proofreadable"]
    )
    op.create_index(
        "ix_paragraphs_content_type", "paragraphs", ["content_type"]
    )
    op.create_index(
        "ix_paragraphs_is_proofreadable", "paragraphs", ["is_proofreadable"]
    )


def downgrade() -> None:
    """Remove content classification columns."""
    # Drop indexes first
    op.drop_index("ix_paragraphs_is_proofreadable", table_name="paragraphs")
    op.drop_index("ix_paragraphs_content_type", table_name="paragraphs")
    op.drop_index("ix_chapters_is_proofreadable", table_name="chapters")
    op.drop_index("ix_chapters_chapter_type", table_name="chapters")

    # Drop columns
    op.drop_column("paragraphs", "is_proofreadable")
    op.drop_column("paragraphs", "content_type")
    op.drop_column("chapters", "is_proofreadable")
    op.drop_column("chapters", "chapter_type")
