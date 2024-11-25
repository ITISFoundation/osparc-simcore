import sqlalchemy as sa

from ._common import NUMERIC_KWARGS, RefActions
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
            ondelete=RefActions.RESTRICT,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Product name",
    ),
    sa.Column(
        "usd_per_credit",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="Price in USD/credit >=0. Must be in sync with Stripe product price (stripe_price_id column in this table).",
    ),
    sa.Column(
        "min_payment_amount_usd",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        server_default=sa.text("10.00"),
        doc="Minimum amount in USD that can be paid for this product.",
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
    sa.Column(
        "stripe_price_id",
        sa.String,
        nullable=False,
        doc="Stripe product price must be in sync with usd_per_credit rate field in this table. Currently created manually in Stripe",
    ),
    sa.Column(
        "stripe_tax_rate_id",
        sa.String,
        nullable=False,
        doc="Stripe tax rate ID associated to this product. Currently created manually in Stripe",
    ),
    sa.CheckConstraint(
        "usd_per_credit >= 0", name="non_negative_usd_per_credit_constraint"
    ),
)


__all__: tuple[str, ...] = ("NUMERIC_KWARGS",)
