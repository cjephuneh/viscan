"""index finished analysis jobs

Revision ID: 016_analysis_job_finished_index
Revises: 015_parallel_ai_phases
Create Date: 2026-11-12

"""

from alembic import op


revision = "016_analysis_job_finished_index"
down_revision = "015_parallel_ai_phases"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_analysis_jobs_status_finished_at",
        "analysis_jobs",
        ["status", "finished_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_analysis_jobs_status_finished_at", table_name="analysis_jobs")
