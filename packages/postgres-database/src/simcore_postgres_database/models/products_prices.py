import sqlalchemy as sa

from ._common import NUMERIC_KWARGS
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
        nullable=False,
        doc="Product name",
    ),
    sa.Column(
        "usd_per_credit",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="Price in USD/credit >=0",
    ),
    sa.Column(
        "comment",
        sa.String,
        nullable=False,
        doc="For the moment a comment on the product owner (PO) who authorized this price",
    ),
    sa.Column(
        "valid_from",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.CheckConstraint(
        "usd_per_credit >= 0", name="non_negative_usd_per_credit_constraint"
    ),
)


__all__: tuple[str, ...] = ("NUMERIC_KWARGS",)
