"""add state type unknown

Revision ID: 06eafd25d004
Revises: ec4f62595e0c
Create Date: 2025-09-01 12:25:25.617790+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "06eafd25d004"
down_revision = "ec4f62595e0c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE statetype ADD VALUE 'UNKNOWN'")


def downgrade() -> None:
    # NOTE: PostgreSQL doesn't support removing enum values directly
    # This downgrades only ensure that StateType.UNKNOWN is not used
    #

    # Find all tables and columns that use statetype enum
    result = op.get_bind().execute(
        sa.DDL(
            """
        SELECT t.table_name, c.column_name, c.column_default
        FROM information_schema.columns c
        JOIN information_schema.tables t ON c.table_name = t.table_name
        WHERE c.udt_name = 'statetype'
        AND t.table_schema = 'public'
    """
        )
    )

    tables_columns = result.fetchall()

    # Update UNKNOWN states to FAILED in all affected tables
    for table_name, column_name, _ in tables_columns:
        op.execute(
            sa.DDL(
                f"""
            UPDATE {table_name}
            SET {column_name} = 'FAILED'
            WHERE {column_name} = 'UNKNOWN'
        """
            )
        )
