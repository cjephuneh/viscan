"""allow parallel analysis and record each AI phase

Revision ID: 015_parallel_ai_phases
Revises: 013_ai_recommendation
Create Date: 2026-11-12

"""

from alembic import op
import sqlalchemy as sa


revision = "015_parallel_ai_phases"
down_revision = "013_ai_recommendation"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_analysis_jobs_one_processing", table_name="analysis_jobs")
    op.add_column(
        "ai_results",
        sa.Column("phase", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade():
    op.drop_column("ai_results", "phase")
    op.create_index(
        "uq_analysis_jobs_one_processing",
        "analysis_jobs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )
