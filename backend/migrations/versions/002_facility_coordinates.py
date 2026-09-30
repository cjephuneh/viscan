"""add facility coordinates

Revision ID: 002_facility_coordinates
Revises: 001_facilities
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "002_facility_coordinates"
down_revision = "001_facilities"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("facilities", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("facilities", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("facilities", "longitude")
    op.drop_column("facilities", "latitude")
