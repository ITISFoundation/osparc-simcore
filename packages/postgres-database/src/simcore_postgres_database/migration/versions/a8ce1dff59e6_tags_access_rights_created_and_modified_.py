"""tags_access_rights created and modified to timestamptz

Revision ID: a8ce1dff59e6
Revises: 52ca673f8778
Create Date: 2026-11-12 13:56:36.049606+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8ce1dff59e6"
down_revision: str | None = "52ca673f8778"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    # The existing values are naive UTC timestamps, so interpret them as UTC
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "tags_access_rights",
        "created",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "tags_access_rights",
        "modified",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "tags_access_rights",
        "modified",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "tags_access_rights",
        "created",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
