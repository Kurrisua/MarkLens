"""Add project-scoped advisor conversation history.

Revision ID: 20260721_0003
Revises: 20260720_0002
"""

from alembic import op
from sqlalchemy import Column, String, inspect

revision = "20260721_0003"
down_revision = "20260720_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in inspect(op.get_bind()).get_columns("consultations")}
    if "project_id" not in columns:
        op.add_column("consultations", Column("project_id", String(36), nullable=True))
    indexes = {item["name"] for item in inspect(op.get_bind()).get_indexes("consultations")}
    if "ix_consultations_project_created" not in indexes:
        op.create_index(
            "ix_consultations_project_created", "consultations", ["project_id", "created_at"]
        )


def downgrade() -> None:
    raise RuntimeError("Project advisor history is intentionally retained on downgrade.")
