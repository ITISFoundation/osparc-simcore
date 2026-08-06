"""Allow null conversation names

Revision ID: 1c5160923b2a
Revises: 9679bf410623
Create Date: 2026-05-20 19:40:17.562565+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1c5160923b2a"
down_revision = "9679bf410623"
branch_labels = None
depends_on = None


def upgrade():
    # Must relax the constraint first before setting existing "null" strings to SQL NULL
    op.alter_column("conversations", "name", existing_type=sa.VARCHAR(), nullable=True)

    # Data migration: convert legacy placeholder strings to SQL NULL
    # 'null'    — literal string stored when name was created as null
    # 'no name' — placeholder stored by old update() when name was cleared
    op.execute("UPDATE conversations SET name = NULL WHERE name IN ('null', 'no name')")


def downgrade():
    # Restore the old placeholder used by the repository when a name was cleared
    op.execute("UPDATE conversations SET name = 'no name' WHERE name IS NULL")

    op.alter_column("conversations", "name", existing_type=sa.VARCHAR(), nullable=False)
