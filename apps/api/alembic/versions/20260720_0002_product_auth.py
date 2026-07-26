"""Add product identity, ownership, learning and audit data.

Revision ID: 20260720_0002
Revises: 20260713_0001
"""

from sqlalchemy import Column, String, inspect

from alembic import op
from app import models  # noqa: F401
from app.db import Base

revision = "20260720_0002"
down_revision = "20260713_0001"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    return name in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # The original teaching migration builds metadata dynamically. create_all keeps a fresh
    # database and an already-initialised development database on the same schema path.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)
    columns = {
        "image_assets": [("owner_id", String(36)), ("project_id", String(36))],
        "cases": [("owner_id", String(36)), ("project_id", String(36))],
        "searches": [("owner_id", String(36))],
        "risk_analyses": [("owner_id", String(36))],
        "document_drafts": [("owner_id", String(36))],
        "consultations": [("owner_id", String(36))],
        "agent_runs": [("owner_id", String(36)), ("visibility", String(32))],
    }
    for table, items in columns.items():
        for name, column_type in items:
            if not _has_column(table, name):
                kwargs = {"nullable": True}
                if table == "agent_runs" and name == "visibility":
                    kwargs = {"nullable": False, "server_default": "user"}
                op.add_column(table, Column(name, column_type, **kwargs))


def downgrade() -> None:
    # Production data is intentionally retained: rolling back this security migration is
    # unsafe once ownership and audit records exist.
    raise RuntimeError("20260720_0002 is not reversible after product data is created")
