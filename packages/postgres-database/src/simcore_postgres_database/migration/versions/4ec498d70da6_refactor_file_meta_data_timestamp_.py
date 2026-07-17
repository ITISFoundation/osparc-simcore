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
    op.alter_column(
        "file_meta_data",
        "created_at",
        existing_type=sa.VARCHAR(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "file_meta_data",
        "last_modified",
        existing_type=sa.VARCHAR(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade():
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
