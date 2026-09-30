"""add analysis jobs queue

Revision ID: 011_analysis_jobs
Revises: 010_seed_facilities
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "011_analysis_jobs"
down_revision = "010_seed_facilities"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("via_image_id", sa.Integer(), nullable=False),
        sa.Column("screening_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("ai_result_id", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ai_result_id"], ["ai_results.id"]),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"]),
        sa.ForeignKeyConstraint(["via_image_id"], ["via_images.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_jobs_via_image_id", "analysis_jobs", ["via_image_id"], unique=False
    )
    op.create_index(
        "ix_analysis_jobs_screening_id", "analysis_jobs", ["screening_id"], unique=False
    )
    op.create_index(
        "ix_analysis_jobs_status_queued_at",
        "analysis_jobs",
        ["status", "queued_at"],
        unique=False,
    )
    op.create_index(
        "uq_analysis_jobs_one_processing",
        "analysis_jobs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_index(
        "uq_analysis_jobs_one_active_image",
        "analysis_jobs",
        ["via_image_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )


def downgrade():
    op.drop_index("uq_analysis_jobs_one_active_image", table_name="analysis_jobs")
    op.drop_index("uq_analysis_jobs_one_processing", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_status_queued_at", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_screening_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_via_image_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
