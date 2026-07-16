"""refactor file_meta_data timestamp columns

Revision ID: a30463871a69
Revises: 31f97453d545
Create Date: 2026-07-15 20:31:47.043304+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a30463871a69"
down_revision = "31f97453d545"
branch_labels = None
depends_on = None


def upgrade():
    # reuse the existing columns in place: convert the type, keep the column names
    op.execute(
        """
        ALTER TABLE file_meta_data
        ALTER COLUMN created_at TYPE timestamptz USING COALESCE(NULLIF(created_at, '')::timestamptz, now()),
        ALTER COLUMN last_modified TYPE timestamptz USING COALESCE(NULLIF(last_modified, '')::timestamptz, now())
        """
    )

    # enforce not-null + default now(), matching column_created_datetime/column_modified_datetime
    op.alter_column("file_meta_data", "created_at", nullable=False, server_default=sa.text("now()"))
    op.alter_column("file_meta_data", "last_modified", nullable=False, server_default=sa.text("now()"))

    # NOTE: no auto-update trigger on `last_modified` here: the storage service sets it
    # explicitly from S3's `last_modified` metadata, so it must not be overwritten.


def downgrade():
    op.alter_column("file_meta_data", "created_at", server_default=None)
    op.alter_column("file_meta_data", "last_modified", server_default=None)

    op.execute(
        """
        ALTER TABLE file_meta_data
        ALTER COLUMN created_at TYPE character varying USING to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SS.US'),
        ALTER COLUMN last_modified TYPE character varying USING to_char(last_modified, 'YYYY-MM-DD"T"HH24:MI:SS.US')
        """
    )

    op.alter_column("file_meta_data", "created_at", nullable=True)
    op.alter_column("file_meta_data", "last_modified", nullable=True)
