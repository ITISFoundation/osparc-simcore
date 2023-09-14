import sqlalchemy as sa

from ._common import NUMERIC_KWARGS, column_created_datetime
from .base import metadata
from .products import products

#
# - Every product has an authorized price
# - The price is valid from the creation date until a new price is created
# - No rows are deleted!
# - If a product has no price, it is assumed zero
#

products_prices = sa.Table(
    "products_prices",
    metadata,
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            products.c.name,
            name="fk_products_prices_product_name",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        doc="Product name",
        index=True,
    ),
    sa.Column(
        "dollars_per_credit",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="Price in dollars per credit >=0",
    ),
    sa.Column(
        "authorized_by",
        sa.BigInteger,
        nullable=False,
        doc="user_id of the product owner (PO) who authorized this price",
    ),
    column_created_datetime(timezone=True),
)
