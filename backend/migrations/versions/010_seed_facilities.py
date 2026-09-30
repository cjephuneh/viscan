"""seed starter facilities

Revision ID: 010_seed_facilities
Revises: 009_assessments
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "010_seed_facilities"
down_revision = "009_assessments"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO facilities (name, type, is_active, created_at, updated_at)
            SELECT v.name, v.type, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM (
                VALUES
                    ('District Hospital', 'District Hospital'),
                    ('Health Centre', 'Health Centre')
            ) AS v(name, type)
            WHERE NOT EXISTS (
                SELECT 1 FROM facilities AS existing WHERE existing.name = v.name
            )
            """
        )
    )


def downgrade():
    op.execute(
        sa.text(
            """
            DELETE FROM facilities
            WHERE name IN ('District Hospital', 'Health Centre')
            """
        )
    )
