"""Initial MySQL evidence-chain schema.

Revision ID: 20260713_0001
Revises: None
"""

from alembic import op
from app import models  # noqa: F401
from app.db import Base

revision = "20260713_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
