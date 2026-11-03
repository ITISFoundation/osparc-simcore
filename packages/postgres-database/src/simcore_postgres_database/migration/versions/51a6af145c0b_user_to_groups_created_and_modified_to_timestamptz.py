"""user_to_groups created and modified to timestamptz

Revision ID: 51a6af145c0b
Revises: 6e4c3c011c6b
Create Date: 2026-11-03 15:01:38.154336+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "51a6af145c0b"
down_revision = "6e4c3c011c6b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "user_to_groups",
        "created",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_to_groups",
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
        "user_to_groups",
        "modified",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_to_groups",
        "created",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
