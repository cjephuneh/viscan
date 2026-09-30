"""add screening patient contact

Revision ID: 012_screening_contact
Revises: 011_analysis_jobs
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "012_screening_contact"
down_revision = "011_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("screenings", sa.Column("phone", sa.String(length=16), nullable=True))
    op.add_column("screenings", sa.Column("notify_channel", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("screenings", "notify_channel")
    op.drop_column("screenings", "phone")
