"""add screenings table

Revision ID: 003_screenings
Revises: 002_facility_coordinates
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "003_screenings"
down_revision = "002_facility_coordinates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "screenings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("patient_code", sa.String(length=32), nullable=False),
        sa.Column("screening_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_code", name="uq_screenings_patient_code"),
    )


def downgrade():
    op.drop_table("screenings")
