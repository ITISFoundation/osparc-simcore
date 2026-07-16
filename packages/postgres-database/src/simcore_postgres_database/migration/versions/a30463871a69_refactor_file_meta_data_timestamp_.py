"""refactor file_meta_data timestamp columns

Revision ID: a30463871a69
Revises: 5f9749ff9007
Create Date: 2026-07-15 20:31:47.043304+00:00

"""

from typing import Final

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a30463871a69"
down_revision = "5f9749ff9007"
branch_labels = None
depends_on = None


# auto-update modified
# TRIGGERS ------------------------
_TABLE_NAME: Final[str] = "file_meta_data"
_TRIGGER_NAME: Final[str] = "auto_update_modified_timestamp"  # NOTE: scoped on table
_PROCEDURE_NAME: Final[str] = f"{_TABLE_NAME}_auto_update_modified_timestamp()"  # NOTE: scoped on database

modified_timestamp_trigger = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS {_TRIGGER_NAME} on {_TABLE_NAME};
CREATE TRIGGER {_TRIGGER_NAME}
BEFORE INSERT OR UPDATE ON {_TABLE_NAME}
FOR EACH ROW EXECUTE PROCEDURE {_PROCEDURE_NAME};
    """
)

# PROCEDURES ------------------------
update_modified_timestamp_procedure = sa.DDL(
    f"""
CREATE OR REPLACE FUNCTION {_PROCEDURE_NAME}
RETURNS TRIGGER AS $$
BEGIN
  NEW.modified := current_timestamp;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
    """
)


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

    # custom
    op.execute(update_modified_timestamp_procedure)
    op.execute(modified_timestamp_trigger)


def downgrade():
    # custom
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} on {_TABLE_NAME};")
    op.execute(f"DROP FUNCTION IF EXISTS {_PROCEDURE_NAME};")

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
