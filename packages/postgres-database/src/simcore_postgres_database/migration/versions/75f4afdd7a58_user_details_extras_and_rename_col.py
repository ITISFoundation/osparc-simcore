"""user_details extras and rename col

Revision ID: 75f4afdd7a58
Revises: 30e8b752e33e
Create Date: 2024-03-15 15:19:38.076627+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "75f4afdd7a58"
down_revision = "30e8b752e33e"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users_pre_registration_details",
        "company_name",
        new_column_name="institution",
        existing_type=sa.String(),
    )
    op.add_column(
        "users_pre_registration_details",
        sa.Column(
            "extras",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )


def downgrade():
    op.alter_column(
        "users_pre_registration_details",
        "institution",
        new_column_name="company_name",
        existing_type=sa.String(),
    )
    op.drop_column("users_pre_registration_details", "extras")
