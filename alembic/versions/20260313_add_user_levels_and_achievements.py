"""Add user levels, XP, and achievements table.

Revision ID: add_levels_achievements
Revises: add_photo_work_document
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "add_levels_achievements"
down_revision = "add_photo_work_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add level columns to users
    op.add_column("users", sa.Column("xp", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("level", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("last_daily_xp", sa.DateTime(timezone=True), nullable=True))

    # Create achievements table
    op.create_table(
        "achievements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("achievements")
    op.drop_column("users", "last_daily_xp")
    op.drop_column("users", "level")
    op.drop_column("users", "xp")
