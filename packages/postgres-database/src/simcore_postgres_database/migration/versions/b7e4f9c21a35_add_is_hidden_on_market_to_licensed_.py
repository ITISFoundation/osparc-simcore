"""add is_hidden_on_market to licensed_resources

Revision ID: b7e4f9c21a35
Revises: 3d6dfe186abe
Create Date: 2026-11-02 15:17:52.000000+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7e4f9c21a35"
down_revision = "3d6dfe186abe"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "licensed_resources",
        sa.Column(
            "is_hidden_on_market",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("licensed_resources", "is_hidden_on_market")
