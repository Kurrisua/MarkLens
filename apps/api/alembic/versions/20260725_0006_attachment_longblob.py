"""Allow project attachments up to the configured upload limit.

Revision ID: 20260725_0006
Revises: 20260724_0005
Create Date: 2026-07-25
"""

from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260725_0006"
down_revision = "20260724_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "project_attachments",
        "raw_content",
        existing_type=mysql.BLOB(),
        type_=mysql.LONGBLOB(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "project_attachments",
        "raw_content",
        existing_type=mysql.LONGBLOB(),
        type_=mysql.BLOB(),
        existing_nullable=False,
    )
