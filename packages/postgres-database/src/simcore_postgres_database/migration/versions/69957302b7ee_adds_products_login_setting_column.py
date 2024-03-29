"""Adds products login.setting column

Revision ID: 69957302b7ee
Revises: 1447a4f5d72b
Create Date: 2023-01-05 21:02:20.063175+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "69957302b7ee"
down_revision = "1447a4f5d72b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "products",
        sa.Column(
            "login_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{\"two_factor_enabled\": false}'::jsonb"),
            nullable=False,
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("products", "login_settings")
    # ### end Alembic commands ###
