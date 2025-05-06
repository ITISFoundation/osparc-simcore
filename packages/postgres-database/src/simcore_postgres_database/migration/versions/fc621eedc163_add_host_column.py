"""Add host column

Revision ID: fc621eedc163
Revises: 0d52976dc616
Create Date: 2025-05-06 09:10:50.968001+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fc621eedc163"
down_revision = "0d52976dc616"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("host", sa.String(), server_default="osparc.io", nullable=True),
    )


def downgrade():
    op.drop_column("products", "host")
