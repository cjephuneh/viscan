"""add ai result recommendation

Revision ID: 013_ai_recommendation
Revises: 012_screening_contact
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "013_ai_recommendation"
down_revision = "012_screening_contact"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_results", sa.Column("recommendation", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("ai_results", "recommendation")
