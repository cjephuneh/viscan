"""Initial VISCAN schema

Revision ID: 001_initial
Revises:
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
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
    with op.batch_alter_table("screenings", schema=None) as batch_op:
        batch_op.create_index(
            "ix_screenings_facility_status", ["facility_id", "status"], unique=False
        )

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("screening_id", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("screening_id"),
    )
    op.create_table(
        "via_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("screening_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["screening_id"], ["screenings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )
    with op.batch_alter_table("via_images", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_via_images_screening_id"), ["screening_id"], unique=False
        )

    op.create_table(
        "ai_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("via_image_id", sa.Integer(), nullable=False),
        sa.Column("prediction", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["via_image_id"], ["via_images.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_results", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ai_results_via_image_id"), ["via_image_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("ai_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_results_via_image_id"))
    op.drop_table("ai_results")

    with op.batch_alter_table("via_images", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_via_images_screening_id"))
    op.drop_table("via_images")

    op.drop_table("assessments")

    with op.batch_alter_table("screenings", schema=None) as batch_op:
        batch_op.drop_index("ix_screenings_facility_status")
    op.drop_table("screenings")

    op.drop_table("facilities")
