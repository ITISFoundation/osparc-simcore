"""file_meta_data: upload_expires_at to timestamp with time zone

Revision ID: a7f3c1d95b02
Revises: 966758d7226c
Create Date: 2026-10-29 14:21:04.512900+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7f3c1d95b02"
down_revision = "966758d7226c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "file_meta_data",
        "upload_expires_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="upload_expires_at AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "file_meta_data",
        "upload_expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="upload_expires_at AT TIME ZONE 'UTC'",
    )
