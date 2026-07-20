"""refactor file_meta_data timestamp columns

Revision ID: 4ec498d70da6
Revises: 1f1779261822
Create Date: 2026-07-17 12:05:33.015512+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ec498d70da6"
down_revision = "1f1779261822"
branch_labels = None
depends_on = None


def upgrade():
    # NOTE: Legacy values are stored as ISO-8601 strings in mixed shapes:
    # offset-aware (`+00:00`/`Z`) and naive (no offset). Pin the transaction to
    # UTC so naive values are anchored to UTC instead of the server's timezone,
    # while offset-aware values keep their explicit offset.
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "file_meta_data",
        "created_at",
        existing_type=sa.VARCHAR(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="created_at::timestamp with time zone",
    )
    op.alter_column(
        "file_meta_data",
        "last_modified",
        existing_type=sa.VARCHAR(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="last_modified::timestamp with time zone",
    )

    # NOTE: `created_at`/`last_modified` are always set by the application before
    # an insert (see FileMetaData/FileMetaDataAtDB models), so no legacy NULLs
    # are expected at this point. Enforce that invariant at the DB level too.
    op.alter_column(
        "file_meta_data",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "file_meta_data",
        "last_modified",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "file_meta_data",
        "last_modified",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "file_meta_data",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    # Emit the string representation in UTC for a deterministic result
    # regardless of the server's timezone.
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "file_meta_data",
        "last_modified",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )
    op.alter_column(
        "file_meta_data",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )
