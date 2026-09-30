"""add ai results table

Revision ID: 007_ai_results
Revises: 006_via_image_index
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "007_ai_results"
down_revision = "006_via_image_index"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("via_image_id", sa.Integer(), nullable=False),
        sa.Column("prediction", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["via_image_id"], ["via_images.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("ai_results")
