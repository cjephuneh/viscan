"""add facilities table

Revision ID: 001_facilities
Revises:
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "001_facilities"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("facilities")
