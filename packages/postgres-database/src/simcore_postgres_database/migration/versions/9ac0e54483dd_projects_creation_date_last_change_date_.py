"""projects creation_date last_change_date to timestamptz

Revision ID: 9ac0e54483dd
Revises: 0dbbba5fcbcb
Create Date: 2026-11-16 10:07:57.874174+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ac0e54483dd"
down_revision: str | None = "0dbbba5fcbcb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    # The existing values are naive UTC timestamps, so interpret them as UTC
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "projects",
        "creation_date",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="creation_date AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "projects",
        "last_change_date",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="last_change_date AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "projects",
        "last_change_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="last_change_date AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "projects",
        "creation_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="creation_date AT TIME ZONE 'UTC'",
    )
