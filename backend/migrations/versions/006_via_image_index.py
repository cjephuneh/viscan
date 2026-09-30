"""index via images by screening

Revision ID: 006_via_image_index
Revises: 005_via_images
Create Date: 2026-09-30

"""

from alembic import op


revision = "006_via_image_index"
down_revision = "005_via_images"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_via_images_screening_id",
        "via_images",
        ["screening_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_via_images_screening_id", table_name="via_images")
