"""groups: created and modified to timestamp with time zone

Revision ID: 18c5c720325e
Revises: a7f3c1d95b02
Create Date: 2026-11-03 06:50:41.148875+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "18c5c720325e"
down_revision = "a7f3c1d95b02"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "groups",
        "created",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "groups",
        "modified",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "groups",
        "modified",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "groups",
        "created",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
