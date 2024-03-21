"""adding stripe fields to product prices

Revision ID: c1d0e98cd289
Revises: 35724106de75
Create Date: 2024-03-01 14:00:03.634947+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c1d0e98cd289"
down_revision = "35724106de75"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "products_prices",
        sa.Column(
            "stripe_price_id",
            sa.String(),
            server_default="stripe price id missing!!",
            nullable=False,
        ),
    )
    op.add_column(
        "products_prices",
        sa.Column(
            "stripe_tax_rate_id",
            sa.String(),
            server_default="stripe tax rate id missing!!",
            nullable=False,
        ),
    )
    # ### end Alembic commands ###

    op.alter_column(
        "products_prices",
        "stripe_price_id",
        server_default=None,
    )
    op.alter_column(
        "products_prices",
        "stripe_tax_rate_id",
        server_default=None,
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("products_prices", "stripe_tax_rate_id")
    op.drop_column("products_prices", "stripe_price_id")
    # ### end Alembic commands ###
