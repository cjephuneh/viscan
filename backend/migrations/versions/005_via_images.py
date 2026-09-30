"""add via images table

Revision ID: 005_via_images
Revises: 004_screening_status_index
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "005_via_images"
down_revision = "004_screening_status_index"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "via_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("screening_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )


def downgrade():
    op.drop_table("via_images")
