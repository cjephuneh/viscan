"""index screenings by facility and status

Revision ID: 004_screening_status_index
Revises: 003_screenings
Create Date: 2026-09-30

"""

from alembic import op


revision = "004_screening_status_index"
down_revision = "003_screenings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_screenings_facility_status",
        "screenings",
        ["facility_id", "status"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_screenings_facility_status", table_name="screenings")
