"""refactor file_meta_data timestamp columns

Revision ID: a30463871a69
Revises: 31f97453d545
Create Date: 2026-07-15 20:31:47.043304+00:00

"""

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


def downgrade():
    op.execute(
        """
        ALTER TABLE file_meta_data
        ALTER COLUMN created_at TYPE character varying USING to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SS.US'),
        ALTER COLUMN last_modified TYPE character varying USING to_char(last_modified, 'YYYY-MM-DD"T"HH24:MI:SS.US')
        """
    )
