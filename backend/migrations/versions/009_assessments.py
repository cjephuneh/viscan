"""add clinician assessments

Revision ID: 009_assessments
Revises: 008_ai_result_index
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "009_assessments"
down_revision = "008_ai_result_index"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("screening_id", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("screening_id"),
    )


def downgrade():
    op.drop_table("assessments")
