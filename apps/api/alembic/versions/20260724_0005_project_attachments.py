"""Add normalized user project attachments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260724_0005"
down_revision = "20260721_0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("project_attachments"):
        op.create_table("project_attachments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), nullable=False), sa.Column("owner_id", sa.String(36), nullable=False), sa.Column("filename", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("raw_content", sa.LargeBinary(), nullable=False), sa.Column("normalized_text", sa.Text(), nullable=False), sa.Column("structure", sa.JSON(), nullable=False), sa.Column("extracted_image_asset_id", sa.String(36)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.ForeignKeyConstraint(["owner_id"], ["users.id"]), sa.ForeignKeyConstraint(["extracted_image_asset_id"], ["image_assets.id"]))
        inspector = inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("project_attachments")}
    if "ix_project_attachments_project_created" not in indexes:
        op.create_index("ix_project_attachments_project_created", "project_attachments", ["project_id", "created_at"])

def downgrade() -> None:
    op.drop_table("project_attachments")
