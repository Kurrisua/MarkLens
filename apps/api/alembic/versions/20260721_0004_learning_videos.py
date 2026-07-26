"""Add curated external learning videos.

Revision ID: 20260721_0004
Revises: 20260721_0003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260721_0004"
down_revision = "20260721_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("learning_videos"):
        op.create_table(
            "learning_videos",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("topic_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("external_url", sa.String(length=700), nullable=False),
            sa.Column("duration_label", sa.String(length=80), nullable=False),
            sa.Column("learning_objective", sa.String(length=500), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("is_published", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["topic_id"], ["learning_topics.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("learning_videos")}
    if "ix_learning_videos_topic_order" not in indexes:
        op.create_index("ix_learning_videos_topic_order", "learning_videos", ["topic_id", "order_index"])


def downgrade() -> None:
    raise RuntimeError("Curated learning video records are intentionally retained on downgrade.")
