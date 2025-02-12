"""new products ui column

Revision ID: 8ec5d2f28966
Revises: 68777fdf9539
Create Date: 2025-02-12 13:00:37.615966+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8ec5d2f28966"
down_revision = "68777fdf9539"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column(
            "ui",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("products", "ui")
