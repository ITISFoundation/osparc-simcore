"""update confirmation created column

Revision ID: 9dddb16914a4
Revises: 06eafd25d004
Create Date: 2025-07-28 17:25:06.534720+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9dddb16914a4"
down_revision = "7e92447558e0"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add new column as nullable first
    op.add_column(
        "confirmations",
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Step 2: Copy data from created_at to created, assuming UTC timezone for existing data
    op.execute(
        "UPDATE confirmations SET created = created_at AT TIME ZONE 'UTC' WHERE created_at IS NOT NULL"
    )

    # Step 3: Make the column non-nullable with default
    op.alter_column(
        "confirmations",
        "created",
        nullable=False,
        server_default=sa.text("now()"),
    )

    # Step 4: Drop old column
    op.drop_column("confirmations", "created_at")


def downgrade():
    # Step 1: Add back the old column
    op.add_column(
        "confirmations",
        sa.Column(
            "created_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
    )

    # Step 2: Copy data back, converting timezone-aware to naive timestamp
    op.execute(
        "UPDATE confirmations SET created_at = created AT TIME ZONE 'UTC' WHERE created IS NOT NULL"
    )

    # Step 3: Make the column non-nullable
    op.alter_column(
        "confirmations",
        "created_at",
        nullable=False,
    )

    # Step 4: Drop new column
    op.drop_column("confirmations", "created")
