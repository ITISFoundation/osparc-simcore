"""products: created and modified to timestamp with time zone

Revision ID: 3d6dfe186abe
Revises: 18c5c720325e
Create Date: 2026-11-03 08:43:49.666479+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3d6dfe186abe"
down_revision = "18c5c720325e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL TIME ZONE 'UTC'")
    op.alter_column(
        "products",
        "created",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "products",
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
        "products",
        "modified",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="modified AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "products",
        "created",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
        postgresql_using="created AT TIME ZONE 'UTC'",
    )
