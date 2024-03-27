"""new phone column in users table

Revision ID: c6185fba2720
Revises: d349f2769a73
Create Date: 2022-08-12 16:58:17.629080+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c6185fba2720"
down_revision = "d349f2769a73"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(), nullable=True))
    op.create_unique_constraint("user_phone_unique_constraint", "users", ["phone"])


def downgrade():
    op.drop_constraint("user_phone_unique_constraint", "users", type_="unique")
    op.drop_column("users", "phone")
