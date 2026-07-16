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
    # new timestamp columns (nullable for now, backfilled below)
    op.add_column("file_meta_data", sa.Column("created", sa.DateTime(timezone=True), nullable=True))
    op.add_column("file_meta_data", sa.Column("modified", sa.DateTime(timezone=True), nullable=True))

    # backfill from the legacy string columns, falling back to now() for null/empty values
    op.execute(
        """
        UPDATE file_meta_data
        SET created = COALESCE(NULLIF(created_at, '')::timestamptz, now()),
            modified = COALESCE(NULLIF(last_modified, '')::timestamptz, now())
        """
    )

    # enforce not-null + default now(), matching column_created_datetime/column_modified_datetime
    op.alter_column("file_meta_data", "created", nullable=False, server_default=sa.text("now()"))
    op.alter_column("file_meta_data", "modified", nullable=False, server_default=sa.text("now()"))

    op.drop_column("file_meta_data", "created_at")
    op.drop_column("file_meta_data", "last_modified")

    # NOTE: no auto-update trigger on `modified` here: the storage service sets it
    # explicitly from S3's `last_modified` metadata, so it must not be overwritten.


def downgrade():
    op.add_column("file_meta_data", sa.Column("last_modified", sa.String(), nullable=True))
    op.add_column("file_meta_data", sa.Column("created_at", sa.String(), nullable=True))

    op.execute(
        """
        UPDATE file_meta_data
        SET created_at = to_char(created, 'YYYY-MM-DD"T"HH24:MI:SS.US'),
            last_modified = to_char(modified, 'YYYY-MM-DD"T"HH24:MI:SS.US')
        """
    )

    op.drop_column("file_meta_data", "modified")
    op.drop_column("file_meta_data", "created")
