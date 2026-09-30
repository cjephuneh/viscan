"""index ai results by image

Revision ID: 008_ai_result_index
Revises: 007_ai_results
Create Date: 2026-09-30

"""

from alembic import op


revision = "008_ai_result_index"
down_revision = "007_ai_results"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_ai_results_via_image_id",
        "ai_results",
        ["via_image_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_ai_results_via_image_id", table_name="ai_results")
